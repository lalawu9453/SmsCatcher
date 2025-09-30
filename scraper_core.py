# --- Selenium 相關匯入 ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
# 📌 優化：webdriver_manager 將只在主程式啟動時呼叫一次。
from selenium.common.exceptions import WebDriverException
from concurrent.futures import ThreadPoolExecutor, as_completed
import tomli
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import re
from bs4 import BeautifulSoup
# --- 讀取設定檔 ---
with open("config.toml", "rb") as f:
    config = tomli.load(f)
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


def check_single_number(number_info, user_agent, service):
    """
    檢查單一號碼的函數，使用傳入的 Selenium Service 實例。
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

        # 每個執行緒獨立啟動 WebDriver，但共用 Chrome 服務路徑 (Service)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        driver.get(number_url)
        # === 優化點 1: 等待第一個訊息列出現 ===
        # 尋找訊息列表的第一行元素，最多等待 10 秒
        message_row_selector = '.container .row.border-bottom'
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, message_row_selector))
        )

        # === 優化點 2: 給 JavaScript 充足的時間執行解密並更新 DOM 內容 ===
        time.sleep(3) # 等待訊息載入
        # 重新從最新的 DOM 抓取內容
        num_soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 尋找所有訊息列
        message_rows = num_soup.select(message_row_selector)
        
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
                
                # === 優化點 3: 檢查是否仍為 Base64 或可讀內容 ===
                # 簡單檢查：如果內容長度過長且包含等號，很可能是 Base64
                if len(sms_content) > 80 or sms_content.endswith('==')or sms_content.endswith('='):
                     sms_content = " 【注意：內容可能被網站加密，請在瀏覽器中確認】"+sms_content

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


def find_active_numbers(CHROME_SERVICE,country_code=COUNTRY_CODE, page=PAGE_INDEX):
    """
    取得所有號碼列表，然後使用執行緒池併發檢查號碼。
    """
    print(f"[*] 正在使用 Selenium 搜尋 {country_code.upper()} 國碼的號碼...")
    numbers_to_check = []
    country_page_url = f"{BASE_URL}/{country_code}/{page}/"
    print(f"[*] 目標國家頁面: {country_page_url}")
    
    # --- 步驟 1: 抓取國家主頁面並取得號碼清單 (只需一個 WebDriver) ---
    driver = None
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent={HEADERS["User-Agent"]}')
        
        print("[*] 正在載入國家頁面以取得號碼清單...")
        # 📌 優化：使用全域的 CHROME_SERVICE
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
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
        # 提交所有任務，並將 CHROME_SERVICE 傳入
        future_to_number = {
            executor.submit(check_single_number, num_info, HEADERS['User-Agent'], CHROME_SERVICE): num_info 
            for num_info in numbers_to_check
        }
        
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                active_numbers.append(result)
                
    print(f"\n[*] 搜尋完畢。總共找到 {len(active_numbers)} 個活躍號碼。")
    return active_numbers
