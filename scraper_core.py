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
import random
import re
from bs4 import BeautifulSoup

# --- 讀取設定檔 ---
# 注意：配置檔案在運行期間不會自動熱更新，如需修改請重啟程式。
with open("config.toml", "rb") as f:
    config = tomli.load(f)

# 讀取區塊內的設定
general_config = config['general']
BASE_URL = general_config['base_urls'][0] # 📌 優化: 目前只使用列表中的第一個 URL
COUNTRY_CODE = general_config['country_code']
CACHE_DURATION_SECONDS = general_config['cache_duration_seconds']
CACHE_DURATION_MINUTES = int(CACHE_DURATION_SECONDS / 60) 
MAX_WORKERS = general_config['max_workers']
PAGE_INDEX = general_config['page_index']
PORT = general_config['port']

# 讀取關鍵字設定
KEYWORDS_CONFIG = config['keywords']

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

def apply_keyword_filter(numbers, include_keywords, exclude_keywords):
    """
    根據關鍵字清單篩選爬蟲結果。
    
    Args:
        numbers (list): 爬蟲結果清單 [{ 'number': ..., 'url': ..., 'last_sms': ... }]
        include_keywords (list): 必須包含的關鍵字 (大小寫不敏感)
        exclude_keywords (list): 必須排除的關鍵字 (大小寫不敏感)

    Returns:
        list: 篩選後的結果清單。
    """
    if not include_keywords and not exclude_keywords:
        return numbers
    
    filtered_numbers = []
    
    # 將關鍵字全部轉為小寫，以便進行不敏感的比對
    inc_lower = [k.lower() for k in include_keywords if k]
    exc_lower = [k.lower() for k in exclude_keywords if k]
    
    for item in numbers:
        is_exc = False
        is_inc = False
        smss = item.get('smss', [])
        for sms in smss:
            sms.lower()
            # 排除邏輯: 如果簡訊內容包含任何排除關鍵字，則跳過
            if any(ex_k in sms for ex_k in exc_lower):
                is_exc=True
                break
            # 包含邏輯: 如果有包含關鍵字清單，則必須包含任一關鍵字
            if inc_lower:
                if any(in_k in sms for in_k in inc_lower):
                    is_inc = True
                    break
        # 通過篩選
        if is_exc and not is_inc and include_keywords:
            continue
        else:
            filtered_numbers.append(item)
        
    return filtered_numbers


def freereceivesms_check_single_number(number_info, user_agent, service):
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
    # 📌 優化：現在將結果包含 sms_content，讓外部篩選器作用
    for i in range(2):  # 最多嘗試2次
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

            # === 瓶頸點: 固定等待 JavaScript 解密內容 ===
            # 為了穩定性，目前仍保留，但這是一個明確的優化目標。
            time.sleep(4) 
            
            # 重新從最新的 DOM 抓取內容
            num_soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # 尋找所有訊息列
            message_rows = num_soup.select(message_row_selector)
            message_rows_contents=[]
            if message_rows:
                latest_row = message_rows[0]
                time_element_lg = latest_row.select_one('.d-none.d-lg-block.col-lg-2 span')
                time_element_sm = latest_row.select_one('.d-block.d-lg-none.ml-2')
                for item in message_rows:
                     item_element = item.select_one('.col-lg-8 div')
                     message_rows_contents.append(item_element.get_text(strip=True) if item_element else "無法讀取簡訊內容。")
                time_text = ''
                if time_element_lg:
                    time_text = time_element_lg.get_text(strip=True)
                elif time_element_sm:
                    time_text = time_element_sm.get_text(strip=True)

                # 抓取簡訊內容
                sms_content_element = latest_row.select_one('.col-lg-8 div')
                sms_content = sms_content_element.get_text(strip=True) if sms_content_element else "無法讀取簡訊內容。"
                    
                # 檢查是否在活躍時間內
                if time_text and is_within_last_hour(time_text):
                    # === 優化點 3: 檢查是否仍為 Base64 或可讀內容 ===
                    if len(sms_content) > 80 and (sms_content.endswith('==') or sms_content.endswith('=')) :
                        sms_content = " 【注意：內容可能被網站加密，請在瀏覽器中確認】"+sms_content

                    # 即使篩選模式是排除，也先回傳結果，讓外部篩選器處理
                    print(f"  -> \033[92m找到活躍號碼 (最新訊息: {time_text})\033[0m")
                    result = {
                        'number': phone_number_text,
                        'url': number_url,
                        'last_sms': sms_content,
                        'smss': message_rows_contents
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
        time.sleep(5)  # 每次嘗試後稍作休息
    
    return result


def freereceivesms_find_active_numbers(CHROME_SERVICE, country_code=COUNTRY_CODE, page=PAGE_INDEX):
    """
    取得所有號碼列表，然後使用執行緒池併發檢查號碼。
    
    返回結果將包含所有活躍號碼，不論是否通過 config.toml 的關鍵字篩選。
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
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.set_page_load_timeout(30)

        driver.get(country_page_url)
        time.sleep(3) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        number_boxes = soup.select('.number-boxes-item')
        if not number_boxes:
            print("[!] 在國家頁面上找不到任何號碼。網站結構可能已更改或載入失敗。")
            return [] # 返回空列表而非 None
        
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
    except Exception as e:
        print(f"\n[!] 載入國家頁面發生一般錯誤: {e}")
        return None
    finally:
        if driver:
            driver.quit() 
            
    # --- 步驟 2: 使用 ThreadPoolExecutor 併發執行檢查 ---
    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任務，並將 CHROME_SERVICE 傳入
        future_to_number = {
            executor.submit(freereceivesms_check_single_number, num_info, HEADERS['User-Agent'], CHROME_SERVICE): num_info 
            for num_info in numbers_to_check
        }
        
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    
    print(f"\n[*] 搜尋完畢。總共找到 {len(raw_active_numbers)} 個活躍號碼。")
    return raw_active_numbers
