# -*- coding: utf-8 -*-
from webdriver_manager.chrome import ChromeDriverManager

import sys
from selenium.webdriver.chrome.service import Service
from flask import Flask, render_template, request, redirect, url_for
from waitress import serve
import threading
import time
import json # 處理 JSON 格式的關鍵字清單
import argparse

import tomli
from scraper_core import scrape_all_sites, apply_keyword_filter

# --- ngrok 相關匯入 ---
from pyngrok import ngrok

# --- 全域變數定義 ---
CHROME_SERVICE = None # 📌 儲存 Selenium Service 實例，避免重複安裝驅動程式。

# --- 讀取設定檔 ---
try:
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
except FileNotFoundError:
    print("[致命錯誤] 找不到 config.toml 檔案，請確認檔案是否存在。")
    sys.exit(1)

# --- 全域設定 ---
NGROK_AUTH_TOKEN = config.get('ngrok_auth_token', '')

# --- ❗️重要設定：處理 Colab 命令行參數 ❗️ ---
try:
    # 查找 --ngrok_token 參數後面的值
    token_index = sys.argv.index('--ngrok_token') + 1
    NGROK_AUTH_TOKEN = sys.argv[token_index]
    print("[配置] 成功從命令行參數讀取 ngrok Token。")
except (ValueError, IndexError):
    if not NGROK_AUTH_TOKEN: # 如果 config.toml 中也沒有，則提示
        print("[配置] 警告：無法從命令行或 config.toml 讀取 ngrok Token。ngrok 將無法啟動。")

# 讀取區塊內的設定
general_config = config['general']
BASE_URLS = general_config['base_urls'] # 📌 優化: 讀取整個列表
COUNTRY_CODE = general_config['country_code']
CACHE_DURATION_SECONDS = general_config['cache_duration_seconds']
CACHE_DURATION_MINUTES = int(CACHE_DURATION_SECONDS / 60) 
PORT = general_config['port']

# 讀取預設關鍵字設定
KEYWORDS_CONFIG = config.get('keywords', {})
KEYWORD_SETTINGS = {
    "filter_mode": KEYWORDS_CONFIG.get('filter_mode', 'contains'),
    "must_include": KEYWORDS_CONFIG.get('must_include', []),
    "must_exclude": KEYWORDS_CONFIG.get('must_exclude', [])
}

# 儲存原始爬蟲結果 (未篩選)
cached_data = {
    "raw_numbers": None, # 儲存未篩選的原始數據
    "timestamp": 0
}

def update_cache(target_urls):
    """
    在背景執行爬蟲並更新快取資料。
    """
    global cached_data
    while True:
        print("\n--- [背景更新] 開始更新資料 ---\n")
        raw_numbers = scrape_all_sites(CHROME_SERVICE, target_urls)
        cached_data["raw_numbers"] = raw_numbers
        cached_data["timestamp"] = time.time()
        
        initial_filtered = apply_keyword_filter(
            raw_numbers if raw_numbers is not None else [],
            KEYWORD_SETTINGS['must_include'], 
            KEYWORD_SETTINGS['must_exclude']
        )
        print(f"--- [背景更新] 資料更新完畢，原始活躍號碼 {len(raw_numbers) if raw_numbers is not None else 0} 個，初始篩選後 {len(initial_filtered)} 個。")
        print(f"--- [背景更新] 將在 {CACHE_DURATION_SECONDS} 秒後再次更新 ---\n")
        print("*"*80)
        
        time.sleep(CACHE_DURATION_SECONDS)

# --- 網頁應用程式 (Flask) ---
app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/', methods=['GET', 'POST'])
def home():
    """
    渲染主頁面，並處理關鍵字篩選器的 POST 請求。
    """
    global KEYWORD_SETTINGS
    
    if request.method == 'POST':
        try:
            include_json = request.form.get('must_include_json')
            exclude_json = request.form.get('must_exclude_json')
            
            new_include = json.loads(include_json) if include_json else []
            new_exclude = json.loads(exclude_json) if exclude_json else []

            KEYWORD_SETTINGS['filter_mode'] = request.form.get('filter_mode', 'none')
            KEYWORD_SETTINGS['must_include'] = new_include
            KEYWORD_SETTINGS['must_exclude'] = new_exclude
            
            print(f"[篩選] 設定已更新: 模式={KEYWORD_SETTINGS['filter_mode']}, 包含={new_include}, 排除={new_exclude}")
            
            return redirect(url_for('home'))
            
        except Exception as e:
            print(f"[錯誤] 處理 POST 請求時發生錯誤: {e}")
            pass

    country_name_map = {'ca': '加拿大', 'us': '美國', 'gb': '英國'}
    country_name = country_name_map.get(COUNTRY_CODE, COUNTRY_CODE.upper())
    last_updated = "正在初始化..."
    
    if cached_data["timestamp"] > 0:
        last_updated = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cached_data["timestamp"]))
    
    raw_numbers = cached_data["raw_numbers"]
    
    if raw_numbers is not None:
        total_count = len(raw_numbers)
        
        mode = KEYWORD_SETTINGS['filter_mode']
        include_k = KEYWORD_SETTINGS['must_include']
        exclude_k = KEYWORD_SETTINGS['must_exclude']

        if mode == 'contains':
            final_include = include_k
            final_exclude = []
        elif mode == 'excludes':
            final_include = []
            final_exclude = exclude_k
        elif mode == 'both':
            final_include = include_k
            final_exclude = exclude_k
        else:
            final_include = []
            final_exclude = []
        
        filtered_numbers = apply_keyword_filter(raw_numbers, final_include, final_exclude)
        filtered_count = len(filtered_numbers)
    else:
        filtered_numbers = None
        total_count = 0
        filtered_count = 0

    return render_template(
        'index.html', 
        numbers=filtered_numbers, 
        country_name=country_name,
        last_updated=last_updated,
        update_min=CACHE_DURATION_MINUTES,
        total_count=total_count,
        filtered_count=filtered_count,
        initial_include=KEYWORD_SETTINGS['must_include'],
        initial_exclude=KEYWORD_SETTINGS['must_exclude'],
        initial_mode=KEYWORD_SETTINGS['filter_mode'],
    )

# --- 主程式執行區塊 ---
if __name__ == '__main__':
    # --- 讀取設定檔中的 ngrok token 作為預設值 ---
    try:
        with open("config.toml", "rb") as f:
            config = tomli.load(f)
        default_ngrok_token = config.get('ngrok_auth_token', '')
    except FileNotFoundError:
        default_ngrok_token = ''

    # --- 設定命令列參數解析 ---
    parser = argparse.ArgumentParser(
        description="臨時簡訊接收與監控工具。",
        formatter_class=argparse.RawTextHelpFormatter # 保持換行格式
    )
    parser.add_argument(
        '--web', 
        type=str, 
        default='all', 
        choices=['1', '2','3','top2' 'all'],
        help=(
            "指定要爬取的網站:\n"
            "  1: 只爬取第一個網頁 預設為freereceivesms.com\n"
            "  2: 只爬取第二個網頁 預設為temp-number.com\n"
            "  3: 只爬取第三個網頁 預設為receive-smss.com/\n"
            "  top2: 預設爬取 freereceivesms.com 和 temp-number.com\n"
            "  all: 爬取設定檔中所有的網站 (預設)"
        )
    )
    parser.add_argument(
        '--ngrok_token',
        type=str,
        default=default_ngrok_token,
        help="您的 ngrok 認證權杖。如果提供，將會覆寫 config.toml 中的設定。"
    )
    args = parser.parse_args()

    # --- 將解析後的值賦給全域變數 ---
    NGROK_AUTH_TOKEN = args.ngrok_token

    # --- 根據參數決定目標 URL ---
    url_map = {
        '1': [BASE_URLS[0]],
        '2': [BASE_URLS[1]],
        '3': [BASE_URLS[2]],
        'top2': [BASE_URLS[0], BASE_URLS[1]], # freereceivesms, temp-number
        'all': BASE_URLS
    }
    target_urls = url_map.get(args.web, BASE_URLS)

    print("[*] 正在檢查並安裝 ChromeDriver...")
    CHROME_SERVICE = Service(ChromeDriverManager().install())
    print("[*] ChromeDriver 服務已就緒。")

    if not NGROK_AUTH_TOKEN:
        print("="*60)
        print("如果只想在本地端執行的話，請確認 config.toml 中的 ngrok_auth_token 為空字串 ''。")
        print("\033[91m[注意] ngrok Authtoken 未設定。\033[0m")
        print("將以本地模式運行 Flask 服務。")
        print("="*60)

    print("="*60)
    print("請確保您已安裝所有必要的套件。建議執行:")
    print("uv sync")
    print("="*60)
    
    update_thread = threading.Thread(target=update_cache, args=(target_urls,), daemon=True)
    update_thread.start()
    
    if NGROK_AUTH_TOKEN:
        try:
            ngrok.set_auth_token(NGROK_AUTH_TOKEN)
            public_url = ngrok.connect(PORT)
            print("="*60)
            print("程式正在啟動...")
            print(f"目標網站列表: {target_urls}")
            print(f"目標國家: {COUNTRY_CODE}")
            print(f" * 本地網址: http://127.0.0.1:{PORT}")
            print(f" * 手機請訪問此公開網址: \033[92m{public_url}\033[0m")
            print("="*60)
            print(f"程式會在背景每 {CACHE_DURATION_MINUTES} 分鐘自動抓取一次最新資料。")
            print("\n\033[91m重要：請保持此視窗開啟，關閉後公開網址將會失效。\033[0m")
            print("="*60)
        except Exception as e:
            print(f"\n[!] ngrok 連線失敗，請檢查您的 Authtoken 或網路狀態: {e}")
            print("將回退到本地模式運行 Flask 服務。")
            print("="*60)
    else:
        print("="*60)
        print("程式正在啟動 (本地模式)...")
        print(f"目標網站列表: {target_urls}")
        print(f"目標國家: {COUNTRY_CODE}")
        print(f" * 本地網址: http://127.0.0.1:{PORT}")
        print("="*60)
        print(f"程式會在背景每 {CACHE_DURATION_MINUTES} 分鐘自動抓取一次最新資料。")
        print("\n\033[91m重要：請保持此視窗開啟。\033[0m")
        print("="*60)        
    
    serve(app, host="0.0.0.0", port=PORT)