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
from lang import get_lang

# --- ngrok 相關匯入 ---
from pyngrok import ngrok

# --- 全域變數定義 ---
CHROME_SERVICE = None # 📌 儲存 Selenium Service 實例，避免重複安裝驅動程式。
lang_dict = get_lang() # 預設為中文，稍後會被 argparse 的結果覆寫

# --- 讀取設定檔 ---
try:
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
except FileNotFoundError:
    print(lang_dict['CONFIG_NOT_FOUND'])
    sys.exit(1)

# --- 全域設定 ---
default_ngrok_token = config.get('ngrok_auth_token', '')

general_config = config['general']
BASE_URLS = general_config['base_urls']
COUNTRY_CODE = general_config['country_code']
CACHE_DURATION_SECONDS = general_config['cache_duration_seconds']
CACHE_DURATION_MINUTES = int(CACHE_DURATION_SECONDS / 60) 
PORT = general_config['port']

KEYWORDS_CONFIG = config.get('keywords', {})
KEYWORD_SETTINGS = {
    "filter_mode": KEYWORDS_CONFIG.get('filter_mode', 'contains'),
    "must_include": KEYWORDS_CONFIG.get('must_include', []),
    "must_exclude": KEYWORDS_CONFIG.get('must_exclude', [])
}

cached_data = {
    "raw_numbers": None,
    "timestamp": 0
}

def update_cache(target_urls, lang_dict):
    """
    在背景執行爬蟲並更新快取資料。
    """
    global cached_data
    while True:
        print(lang_dict['UPDATE_START'])
        raw_numbers = scrape_all_sites(CHROME_SERVICE, target_urls, lang_dict)
        cached_data["raw_numbers"] = raw_numbers
        cached_data["timestamp"] = time.time()
        
        initial_filtered = apply_keyword_filter(
            raw_numbers if raw_numbers is not None else [],
            KEYWORD_SETTINGS['must_include'], 
            KEYWORD_SETTINGS['must_exclude']
        )
        print(lang_dict['UPDATE_DONE'].format(
            raw_count=len(raw_numbers) if raw_numbers is not None else 0, 
            filtered_count=len(initial_filtered)
        ))
        print(lang_dict['UPDATE_NEXT'].format(seconds=CACHE_DURATION_SECONDS))
        print("*"*80)
        
        time.sleep(CACHE_DURATION_SECONDS)

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
            
            print(lang_dict['FILTER_UPDATED'].format(
                mode=KEYWORD_SETTINGS['filter_mode'], 
                include=new_include, 
                exclude=new_exclude
            ))
            
            return redirect(url_for('home'))
            
        except Exception as e:
            print(lang_dict['POST_REQUEST_ERROR'].format(e=e))
            pass

    country_name_map = {'ca': 'Canada', 'us': 'United States', 'gb': 'United Kingdom'}
    country_name = country_name_map.get(COUNTRY_CODE, COUNTRY_CODE.upper())
    last_updated = lang_dict['INITIALIZING']
    
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
        lang=lang_dict  # 將語言字典傳遞給模板
    )

@app.route('/test-ui')
def test_ui():
    """
    渲染一個帶有假資料的測試頁面，用於 UI/UX 驗證。
    """
    mock_sms_data = [
        {
            'source': 'freereceivesms',
            'number': '+11234567890',
            'time': '5 minutes ago',
            'last_sms': 'Your verification code for [freereceivesms] is 12345. This is a test message.'
        },
        {
            'source': 'receive-sms',
            'number': '+449876543210',
            'time': '10 minutes ago',
            'last_sms': 'Hello from [receive-smss]! Your package will be delivered tomorrow.'
        },
        {
            'source': 'temp-number',
            'number': '+15555555555',
            'time': '1 hour ago',
            'last_sms': '[temp-number] security alert: A new device has been logged into your account.'
        },
        {
            'source': 'freereceivesms',
            'number': '+11234567890',
            'time': '2 hours ago',
            'last_sms': 'Another test message from [freereceivesms].'
        }
    ]
    
    country_name_map = {'ca': 'Canada', 'us': 'United States', 'gb': 'United Kingdom'}
    country_name = country_name_map.get(COUNTRY_CODE, COUNTRY_CODE.upper())

    return render_template(
        'index.html',
        numbers=mock_sms_data,
        country_name=country_name,
        last_updated="UI Test Mode",
        update_min=99,
        total_count=len(mock_sms_data),
        filtered_count=len(mock_sms_data),
        initial_include=[],
        initial_exclude=[],
        initial_mode='none',
        lang=lang_dict
    )

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Temporary SMS Receiver and Monitor.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--web', 
        type=str, 
        default='all', 
        choices=['1', '2', '3','top2', 'all'],
        help=(
            "Specify websites to scrape:\n"
            "  1: Scrape url index1\n"
            "  2: Scrape url index2\n"
            "  3: Scrape url index3\n"
            "  top2: Scrape top2 url \n"
            "  all: Scrape all websites from config (default)"
        )
    )
    parser.add_argument(
        '--ngrok_token',
        type=str,
        default=default_ngrok_token,
        help="Your ngrok authentication token. Overrides the value in config.toml."
    )
    parser.add_argument(
        '--lan',
        type=str,
        default='zh',
        choices=['zh', 'en'],
        help="Set the display language for console output (zh/en). Default is zh."
    )
    parser.add_argument(
        '--test-ui',
        action='store_true',
        help="Run in UI test mode. Starts the server without web scraping."
    )
    args = parser.parse_args()

    # 語言設定應優先處理
    lang_dict = get_lang(args.lan)

    if args.test_ui:
        print("="*60)
        print("🚀 Running in UI Test Mode!")
        print("   Background scraping is DISABLED.")
        print(f"✅ Access the test page at: http://127.0.0.1:{PORT}/test-ui")
        print("="*60)
    else:
        # --- 只有在非測試模式下才執行爬蟲和 ngrok 相關邏輯 ---
        NGROK_AUTH_TOKEN = args.ngrok_token

        url_map = {
            '1': [BASE_URLS[0]],
            '2': [BASE_URLS[1]],
            '3': [BASE_URLS[2]],
            'top2': [BASE_URLS[0], BASE_URLS[1]],
            'all': BASE_URLS
        }
        target_urls = url_map.get(args.web, BASE_URLS)

        print(lang_dict['CHECKING_DRIVER'])
        CHROME_SERVICE = Service(ChromeDriverManager().install())
        print(lang_dict['DRIVER_READY'])

        if not NGROK_AUTH_TOKEN:
            print("="*60)
            print(lang_dict['NGROK_REMINDER'])
            print(lang_dict['NGROK_NOT_SET'])
            print(lang_dict['RUN_LOCAL_MODE'])
            print("="*60)

        print("="*60)
        print(lang_dict['INSTALL_DEPS'])
        print("uv sync")
        print("="*60)
        
        update_thread = threading.Thread(target=update_cache, args=(target_urls, lang_dict), daemon=True)
        update_thread.start()
        
        if NGROK_AUTH_TOKEN:
            try:
                ngrok.set_auth_token(NGROK_AUTH_TOKEN)
                public_url = ngrok.connect(PORT)
                print("="*60)
                print(lang_dict['APP_STARTING'])
                print(lang_dict['TARGET_SITES'].format(urls=target_urls))
                print(lang_dict['TARGET_COUNTRY'].format(country=COUNTRY_CODE))
                print(lang_dict['LOCAL_URL'].format(port=PORT))
                print(lang_dict['PUBLIC_URL'].format(url=public_url))
                print("="*60)
                print(lang_dict['BACKGROUND_UPDATE_INFO'].format(minutes=CACHE_DURATION_MINUTES))
                print(lang_dict['KEEP_WINDOW_OPEN_NGROK'])
                print("="*60)
            except Exception as e:
                print(lang_dict['NGROK_FAIL'].format(e=e))
                print(lang_dict['FALLBACK_LOCAL'])
                print("="*60)
        else:
            print("="*60)
            print(lang_dict['APP_STARTING_LOCAL'])
            print(lang_dict['TARGET_SITES'].format(urls=target_urls))
            print(lang_dict['TARGET_COUNTRY'].format(country=COUNTRY_CODE))
            print(lang_dict['LOCAL_URL'].format(port=PORT))
            print("="*60)
            print(lang_dict['BACKGROUND_UPDATE_INFO'].format(minutes=CACHE_DURATION_MINUTES))
            print(lang_dict['KEEP_WINDOW_OPEN_LOCAL'])
            print("="*60)        
    
    # --- Flask 伺服器在所有模式下都會啟動 ---
    serve(app, host="0.0.0.0", port=PORT)