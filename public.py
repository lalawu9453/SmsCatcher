# -*- coding: utf-8 -*-
from webdriver_manager.chrome import ChromeDriverManager

import sys
from selenium.webdriver.chrome.service import Service
from flask import Flask, render_template_string
from waitress import serve
import threading
import time

import tomli
from scraper_core import find_active_numbers   

# --- ngrok 相關匯入 ---
from pyngrok import ngrok

# --- 全域變數定義 ---
CHROME_SERVICE = None # 📌 儲存 Selenium Service 實例，避免重複安裝驅動程式。

# --- 讀取設定檔 ---
with open("config.toml", "rb") as f:
    config = tomli.load(f)

# --- 全域設定 ---
# 預設從 config.toml 讀取
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
BASE_URL = general_config['base_url']
COUNTRY_CODE = general_config['country_code']
CACHE_DURATION_SECONDS = general_config['cache_duration_seconds']
CACHE_DURATION_MINUTES = int(CACHE_DURATION_SECONDS / 60) 
PORT = general_config['port']

cached_data = {
    "numbers": None,
    "timestamp": 0
}

def update_cache():
    """
    在背景執行爬蟲並更新快取資料。
    """
    global cached_data
    while True:
        print("\n--- [背景更新] 開始更新資料 ---")
        numbers = find_active_numbers(CHROME_SERVICE)
        cached_data["numbers"] = numbers
        cached_data["timestamp"] = time.time()
        print(f"--- [背景更新] 資料更新完畢，將在 {CACHE_DURATION_SECONDS} 秒後再次更新 ---\n")
        time.sleep(CACHE_DURATION_SECONDS)

# --- 網頁應用程式 (Flask) ---
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>最近一小時內活躍的簡訊號碼</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f4f7f9; color: #333; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: flex-start; min-height: 10vh; }
        .container { background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); width: 100%; max-width: 800px; text-align: center; }
        h1 { color: #0056b3; margin-bottom: 10px; }
        h1 span { font-size: 1.2rem; color: #555; vertical-align: middle; }
        p.info { font-size: 0.9em; color: #777; margin-top: 0; margin-bottom: 20px; }
        ul { list-style-type: none; padding: 0; }
        li { 
            background-color: #e9f5ff; 
            margin: 15px 0; 
            padding: 15px; 
            border-radius: 8px; 
            border-left: 5px solid #007bff; 
            text-align: left;
            transition: transform 0.2s, box-shadow 0.2s; 
        }
        li:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1); }
        a { 
            text-decoration: none; 
            color: #007bff; 
            font-weight: bold; 
            font-size: 1.2em; 
            transition: color 0.2s;
            display: block;
            margin-bottom: 8px;
        }
        a:hover { color: #0056b3; }
        .sms-content {
            font-size: 0.95em;
            color: #343a40;
            margin: 0;
            padding: 10px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            word-wrap: break-word;
        }
        .error, .no-results { font-size: 1.1em; color: #777; font-style: italic; padding: 20px; }
        .error { color: #d9534f; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>最近一小時內活躍的簡訊號碼 <span>({{ country_name }})</span></h1>
        <p class="info">頁面每 {{ update_min }} 分鐘自動刷新。上次更新於 {{ last_updated }}</p>
        <div id="results">
            {% if numbers is none %}
                <p class="error">讀取網站時發生錯誤，請稍後再試。爬蟲可能已被封鎖或初始化失敗。</p>
            {% elif numbers %}
                <ul>
                    {% for item in numbers %}
                        <li>
                            <a href="{{ item.url }}" target="_blank" rel="noopener noreferrer">{{ item.number }}</a>
                            <p class="sms-content">{{ item.last_sms }}</p>
                        </li>
                    {% endfor %}
                </ul>
            {% else %}
                <p class="no-results">目前沒有在最近一小時內收到簡訊的號碼。</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    """
    渲染主頁面，顯示快取中的資料。
    """
    country_name_map = {'ca': '加拿大', 'us': '美國', 'gb': '英國'}
    country_name = country_name_map.get(COUNTRY_CODE, COUNTRY_CODE.upper())
    last_updated = "正在初始化..."
    if cached_data["timestamp"] > 0:
        last_updated = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cached_data["timestamp"]))

    return render_template_string(
        HTML_TEMPLATE, 
        numbers=cached_data["numbers"], 
        country_name=country_name,
        last_updated=last_updated,
        update_min=CACHE_DURATION_MINUTES
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
        print("將以本地模式運行 Flask 服務。在Colab無法顯示網頁。")
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
