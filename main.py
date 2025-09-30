# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import re
from flask import Flask, render_template_string
from waitress import serve
import threading
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import tomli

# --- Selenium 相關匯入 ---
# 我們需要 Selenium 來模擬真實的瀏覽器行為，以繞過網站的防爬蟲保護
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException

# --- ngrok 相關匯入 ---
from pyngrok import ngrok

'''
這個版本使用 Selenium 來模擬瀏覽器行為，並使用 ngrok 來建立公開的網址。
'''
# --- 讀取設定檔 ---
with open("config.toml", "rb") as f:
    config = tomli.load(f)

# --- 全域設定 ---
# 直接讀取，無需轉換型別
NGROK_AUTH_TOKEN = config['ngrok_auth_token']

# 讀取區塊內的設定
general_config = config['general']
BASE_URL = general_config['base_url']
COUNTRY_CODE = general_config['country_code']
CACHE_DURATION_SECONDS = general_config['cache_duration_seconds']
CACHE_DURATION_MINUTES = int(CACHE_DURATION_SECONDS / 60) 
MAX_WORKERS = general_config['max_workers']
PAGE_INDEX = general_config['page_index']
PORT = general_config['port']

# 偽裝成瀏覽器的 Headers
HEADERS = config['headers']


cached_data = {
    "numbers": None,
    "timestamp": 0
}

# --- 核心功能 ---

def is_within_last_hour(time_text):
    """
    檢查時間文字 (例如 '5分钟前', '2小时前') 是否在最近一小時內。
    """
    time_text = time_text.strip()
    # 檢查 "分钟前" (分鐘前) 或 "minutes ago"
    if any(s in time_text for s in ['分钟前', '分鐘前', 'minutes ago']):
        try:
            minutes = int(re.findall(r'\d+', time_text)[0])
            if minutes <= 60:
                return True
        except (IndexError, ValueError):
            return False
    # "秒前" (秒前) 或 "seconds ago" 也算在內
    if any(s in time_text for s in ['秒前', 'seconds ago']):
        return True
    return False

def check_single_number(number_info, user_agent):
    """
    檢查單一號碼的函數，每個執行緒會獨立運行一個 WebDriver 實例。
    """
    number_url = number_info['url']
    phone_number_text = number_info['number']

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'user-agent={user_agent}')
    
    driver = None
    result = None
    try:
        print(f"    [THREAD] 檢查號碼: {phone_number_text} ...", end="", flush=True)

        # 每個執行緒獨立啟動 WebDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        driver.get(number_url)
        time.sleep(2) # 等待訊息載入
        
        num_soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 尋找所有訊息列 (與 main.py 邏輯相同)
        message_rows = num_soup.select('.container .row.border-bottom')
        
        if message_rows:
            latest_row = message_rows[0]
            time_element_lg = latest_row.select_one('.d-none.d-lg-block.col-lg-2 span')
            time_element_sm = latest_row.select_one('.d-block.d-lg-none.ml-2')
            
            time_text = ''
            if time_element_lg:
                time_text = time_element_lg.get_text(strip=True)
            elif time_element_sm:
                time_text = time_element_sm.get_text(strip=True)

            if time_text and is_within_last_hour(time_text):
                # 抓取簡訊內容
                sms_content_element = latest_row.select_one('.col-lg-8 div')
                sms_content = sms_content_element.get_text(strip=True) if sms_content_element else "無法讀取簡訊內容。"
                
                print(f"  -> \033[92m找到活躍號碼 (最新訊息: {time_text})\033[0m")
                result = {
                    'number': phone_number_text,
                    'url': number_url,
                    'last_sms': sms_content
                }
            else:
                print(f"  -> 不活躍 (最新訊息: {time_text})")
        else:
            print("  -> 找不到訊息列。")

    except WebDriverException as e:
        print(f"  -> \033[91mSelenium 讀取失敗: {e}\033[0m")
    except Exception as e:
        print(f"  -> 檢查 {phone_number_text} 失敗: {e}")
    finally:
        if driver:
            driver.quit()
    return result

def find_active_numbers(country_code=COUNTRY_CODE,page=PAGE_INDEX):
    """
    (優化後) 取得所有號碼列表，然後使用執行緒池併發檢查號碼。
    """
    print(f"[*] 正在使用 Selenium 搜尋 {country_code.upper()} 國碼的號碼...")
    numbers_to_check = []
    country_page_url = f"{BASE_URL}/{country_code}/{page}/"
    print(f"[*] 目標國家頁面: {country_page_url}")
    # --- [修正] 步驟 1: 抓取國家主頁面並取得號碼清單 (從 main.py 移植) ---
    driver = None
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent={HEADERS["User-Agent"]}')
        
        print("[*] 正在載入國家頁面以取得號碼清單...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)

        driver.get(country_page_url)
        time.sleep(3) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        number_boxes = soup.select('.number-boxes-item')
        if not number_boxes:
            print("[!] 在國家頁面上找不到任何號碼。網站結構可能已更改或載入失敗。")
            return None
        
        for box in number_boxes:
            link_tag = box.find('a', class_='btn-outline-info')
            if not link_tag or 'href' not in link_tag.attrs:
                continue
            
            number_path = link_tag['href']
            number_url = f"{BASE_URL}{number_path}"
            phone_number_text = box.find('h4').get_text(strip=True) if box.find('h4') else "N/A"
            numbers_to_check.append({'number': phone_number_text, 'url': number_url})
        
        print(f"[*] 成功找到 {len(numbers_to_check)} 個號碼，開始併發檢查...")
        
    except WebDriverException as e:
        print(f"\n[!] 載入國家頁面失敗: {e}")
        return None
    finally:
        if driver:
            driver.quit() 
            
    # --- 步驟 2: 使用 ThreadPoolExecutor 併發執行檢查 ---
    active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任務
        future_to_number = {
            executor.submit(check_single_number, num_info, HEADERS['User-Agent']): num_info 
            for num_info in numbers_to_check
        }
        
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                active_numbers.append(result)
                
    print(f"\n[*] 搜尋完畢。總共找到 {len(active_numbers)} 個活躍號碼。")
    return active_numbers


# --- 背景更新資料的執行緒 (與 main.py 相同) ---

def update_cache():
    """
    在背景執行爬蟲並更新快取資料。
    """
    global cached_data
    while True:
        print("\n--- [背景更新] 開始更新資料 ---")
        numbers = find_active_numbers()
        cached_data["numbers"] = numbers
        cached_data["timestamp"] = time.time()
        print(f"--- [背景更新] 資料更新完畢，將在 {CACHE_DURATION_SECONDS} 秒後再次更新 ---\n")
        time.sleep(CACHE_DURATION_SECONDS)

# --- 網頁應用程式 (Flask) (與 main.py 相同) ---
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
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f4f7f9; color: #333; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; }
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
    # 檢查 ngrok Authtoken 是否已設定
    if NGROK_AUTH_TOKEN == "在此貼上你的 ngrok Authtoken" :
        print("="*60)
        print("如果只想在本地端執行的話，直接把NGROK_AUTH_TOKEN=''，設定為空字串即可。")
        print("\033[91m[錯誤] 尚未設定 ngrok Authtoken！\033[0m")
        print("請按照以下步驟操作：")
        print("1. 打開 .py 檔案。")
        print("2. 找到 `NGROK_AUTH_TOKEN` 這一行。")
        print("3. 到 https://dashboard.ngrok.com/get-started/your-authtoken 取得您的金鑰。")
        print("4. 將金鑰貼在引號中，然後儲存檔案並重新執行。")
        print("="*60)
        sys.exit(1) # 結束程式

    # 提示使用者安裝新套件
    print("="*60)
    print("重要提示：此版本已更新為使用 Selenium 和 ngrok。")
    print("請確保您已安裝所有必要的套件。")
    print("請在終端機執行:")
    print("uv sync")
    print("="*60)
    
    # 在背景啟動更新執行緒
    update_thread = threading.Thread(target=update_cache, daemon=True)
    update_thread.start()
    
    # --- 設定並啟動 ngrok 通道 ---
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
        print("第一次執行時，webdriver-manager 會自動下載驅動程式，請耐心等候。")
        print("\n\033[91m重要：請保持此視窗開啟，關閉後公開網址將會失效。\033[0m")
        print("="*60)
    except Exception as e:
        print(f"\n[!] ngrok 連線失敗，請檢查您的 Authtoken 或網路狀態: {e}")
        print("將繼續以本地模式運行 Flask 服務。")
        print("="*60)
        print("程式正在啟動...")
        print(f"目標網站: {BASE_URL}/{COUNTRY_CODE}/")
        print(f" * 本地網址: http://127.0.0.1:{PORT}")
        print("="*60)
        print(f"程式會在背景每 {CACHE_DURATION_MINUTES} 分鐘自動抓取一次最新資料。")
        print("第一次執行時，webdriver-manager 會自動下載驅動程式，請耐心等候。")
        print("\n\033[91m重要：請保持此視窗開啟，關閉後公開網址將會失效。\033[0m")
        print("="*60)
        
    # 啟動網頁伺服器
    serve(app, host="0.0.0.0", port=5000)
