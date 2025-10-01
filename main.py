# -*- coding: utf-8 -*-
from webdriver_manager.chrome import ChromeDriverManager

import sys
from selenium.webdriver.chrome.service import Service
from flask import Flask, render_template, request, redirect, url_for
from waitress import serve
import threading
import time
import json # 處理 JSON 格式的關鍵字清單

import tomli
from scraper_core import freereceivesms_find_active_numbers, apply_keyword_filter   

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
BASE_URL = general_config['base_urls'][0] # 📌 優化: 目前只使用列表中的第一個 URL
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

if BASE_URL == "https://www.freereceivesms.com":
    print("注意：freereceivesms.com 可能會封鎖爬蟲，導致無法取得資料。如果發生錯誤，請稍後再試。")

    
# 儲存原始爬蟲結果 (未篩選)
cached_data = {
    "raw_numbers": None, # 儲存未篩選的原始數據
    "timestamp": 0
}

def update_cache():
    """
    在背景執行爬蟲並更新快取資料。
    """
    global cached_data
    while True:
        print("\n--- [背景更新] 開始更新資料 ---\n")
        if BASE_URL == "https://www.freereceivesms.com":
            # 這裡呼叫的爬蟲函數應返回未篩選的原始數據
            raw_numbers = freereceivesms_find_active_numbers(CHROME_SERVICE)
            cached_data["raw_numbers"] = raw_numbers
            cached_data["timestamp"] = time.time()
            
            # 執行一次初始篩選，印出日誌
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
    
    # 處理 POST 請求 (使用者提交篩選表單)
    if request.method == 'POST':
        try:
            # 讀取 JSON 格式的關鍵字清單
            include_json = request.form.get('must_include_json')
            exclude_json = request.form.get('must_exclude_json')
            
            new_include = json.loads(include_json) if include_json else []
            new_exclude = json.loads(exclude_json) if exclude_json else []

            # 更新全域篩選設定
            KEYWORD_SETTINGS['filter_mode'] = request.form.get('filter_mode', 'none')
            KEYWORD_SETTINGS['must_include'] = new_include
            KEYWORD_SETTINGS['must_exclude'] = new_exclude
            
            print(f"[篩選] 設定已更新: 模式={KEYWORD_SETTINGS['filter_mode']}, 包含={new_include}, 排除={new_exclude}")
            
            # 重新導向回 GET 請求，以避免使用者刷新時重複提交
            return redirect(url_for('home'))
            
        except Exception as e:
            print(f"[錯誤] 處理 POST 請求時發生錯誤: {e}")
            # 即使出錯也繼續渲染頁面
            pass

    # --- GET 請求渲染邏輯 ---
    country_name_map = {'ca': '加拿大', 'us': '美國', 'gb': '英國'}
    country_name = country_name_map.get(COUNTRY_CODE, COUNTRY_CODE.upper())
    last_updated = "正在初始化..."
    
    # 1. 準備快取時間
    if cached_data["timestamp"] > 0:
        last_updated = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cached_data["timestamp"]))
    
    raw_numbers = cached_data["raw_numbers"]
    
    # 2. 進行篩選
    if raw_numbers is not None:
        total_count = len(raw_numbers)
        
        mode = KEYWORD_SETTINGS['filter_mode']
        include_k = KEYWORD_SETTINGS['must_include']
        exclude_k = KEYWORD_SETTINGS['must_exclude']

        # 根據模式設定包含和排除清單
        if mode == 'contains':
            final_include = include_k
            final_exclude = []
        elif mode == 'excludes':
            final_include = []
            final_exclude = exclude_k
        elif mode == 'both':
            final_include = include_k
            final_exclude = exclude_k
        else: # 'none' 或其他未知模式
            final_include = []
            final_exclude = []
        
        # 執行篩選
        filtered_numbers = apply_keyword_filter(raw_numbers, final_include, final_exclude)
        filtered_count = len(filtered_numbers)
    else:
        # 爬蟲失敗或未初始化
        filtered_numbers = None
        total_count = 0
        filtered_count = 0

    return render_template(
        'index.html', 
        numbers=filtered_numbers, 
        country_name=country_name,
        last_updated=last_updated,
        update_min=CACHE_DURATION_MINUTES,
        
        # 傳遞給前端顯示的篩選統計
        total_count=total_count,
        filtered_count=filtered_count,
        
        # 傳遞當前篩選設定給 JavaScript/表單
        initial_include=KEYWORD_SETTINGS['must_include'],
        initial_exclude=KEYWORD_SETTINGS['must_exclude'],
        initial_mode=KEYWORD_SETTINGS['filter_mode'],
    )

# --- 主程式執行區塊 ---
if __name__ == '__main__':
    # 📌 優化：僅在啟動時安裝一次 WebDriver
    print("[*] 正在檢查並安裝 ChromeDriver...")
    CHROME_SERVICE = Service(ChromeDriverManager().install())
    print("[*] ChromeDriver 服務已就緒。")

    # 檢查 ngrok Authtoken 是否已設定
    if not NGROK_AUTH_TOKEN: # 檢查是否為空字串
        print("="*60)
        print("如果只想在本地端執行的話，請確認 config.toml 中的 ngrok_auth_token 為空字串 ''。")
        print("\033[91m[注意] ngrok Authtoken 未設定。\033[0m")
        print("將以本地模式運行 Flask 服務。")
        print("="*60)

    # 提示使用者安裝新套件
    print("="*60)
    print("請確保您已安裝所有必要的套件。建議執行:")
    print("uv sync")
    print("="*60)
    
    # 在背景啟動更新執行緒
    update_thread = threading.Thread(target=update_cache, daemon=True)
    update_thread.start()
    
    # --- 設定並啟動 ngrok 通道 (如果 Token 存在) ---
    if NGROK_AUTH_TOKEN:
        try:
            ngrok.set_auth_token(NGROK_AUTH_TOKEN)
            public_url = ngrok.connect(PORT)
            print("="*60)
            print("程式正在啟動...")
            print(f"目標網站: {BASE_URL}/{COUNTRY_CODE}/")
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
        # 如果沒有 Token，則只顯示本地網址
        print("="*60)
        print("程式正在啟動 (本地模式)...")
        print(f"目標網站: {BASE_URL}/{COUNTRY_CODE}/")
        print(f" * 本地網址: http://127.0.0.1:{PORT}")
        print("="*60)
        print(f"程式會在背景每 {CACHE_DURATION_MINUTES} 分鐘自動抓取一次最新資料。")
        print("\n\033[91m重要：請保持此視窗開啟。\033[0m")
        print("="*60)
        
    # 啟動網頁伺服器
    # 這裡使用 waitrsss.serve() 是一個很好的選擇，比 Flask 內建伺服器更適合生產環境。
    serve(app, host="0.0.0.0", port=PORT)
