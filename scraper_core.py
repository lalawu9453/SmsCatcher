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
import os
import requests
import zipfile
import io

# --- 讀取設定檔 ---
# 注意：配置檔案在運行期間不會自動熱更新，如需修改請重啟程式。
with open("config.toml", "rb") as f:
    config = tomli.load(f)

# --- 全域設定 ---
general_config = config['general']
COUNTRY_CODE = general_config['country_code']
CACHE_DURATION_SECONDS = general_config['cache_duration_seconds']
CACHE_DURATION_MINUTES = int(CACHE_DURATION_SECONDS / 60) 
MAX_WORKERS = general_config['max_workers']
PAGE_INDEX = general_config['page_index']
PORT = general_config['port']
KEYWORDS_CONFIG = config['keywords']
HEADERS = config['headers']

# --- 廣告攔截外掛設定 ---
UBLOCK_URL = "https://github.com/gorhill/uBlock/releases/download/1.57.2/uBlock0_1.57.2.chromium.zip"
EXTENSION_PATH = os.path.join(os.getcwd(), "extensions", "ublock_origin")

def setup_adblocker():
    """
    檢查、下載並解壓縮 uBlock Origin 廣告攔截外掛。
    """
    if os.path.isdir(EXTENSION_PATH):
        # print("[*] uBlock Origin 已存在，跳過下載。")
        return
    
    print("[*] 廣告攔截外掛不存在，正在從 GitHub 下載...")
    try:
        r = requests.get(UBLOCK_URL, stream=True)
        r.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            os.makedirs(EXTENSION_PATH, exist_ok=True)
            z.extractall(EXTENSION_PATH)
        print(f"[*] 廣告攔截外掛已成功安裝至: {EXTENSION_PATH}")
        
    except requests.exceptions.RequestException as e:
        print(f"\n[!] 下載廣告攔截外掛失敗: {e}")
    except zipfile.BadZipFile:
        print("\n[!] 下載的檔案非有效的 ZIP 檔案。")
    except Exception as e:
        print(f"\n[!] 安裝廣告攔截外掛時發生未知錯誤: {e}")

def create_adblocking_options(user_agent):
    """
    建立並回傳一個已載入廣告攔截外掛的 ChromeOptions 物件。
    """
    setup_adblocker() # 確保外掛已安裝
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'user-agent={user_agent}')
    
    if os.path.isdir(EXTENSION_PATH):
        options.add_argument(f'--load-extension={EXTENSION_PATH}')
        # print("[*] 已成功載入廣告攔截外掛。")
    else:
        print("[!] 警告：廣告攔截外掛目錄不存在，瀏覽器將在無攔截模式下運行。")
        
    return options

def is_within_last_hour(time_text):
    """
    檢查時間文字 (例如 '5分钟前', '2小时前') 是否在最近一小時內。
    """
    time_text = time_text.strip()
    if any(s in time_text for s in ['分钟前', '分鐘前', 'minutes ago']):
        try:
            minutes = int(re.findall(r'\d+', time_text)[0])
            if minutes <= 60:
                return True
        except (IndexError, ValueError):
            return False
    if any(s in time_text for s in ['秒前', 'seconds ago']):
        return True
    return False

def apply_keyword_filter(numbers, include_keywords, exclude_keywords):
    """
    根據關鍵字清單篩選爬蟲結果。
    """
    if not include_keywords and not exclude_keywords:
        return numbers

    filtered_numbers = []
    inc_lower = [k.lower() for k in include_keywords if k]
    exc_lower = [k.lower() for k in exclude_keywords if k]

    for item in numbers:
        all_sms_content = " ".join(item.get('smss', [])).lower()
        if exc_lower and any(ex_k in all_sms_content for ex_k in exc_lower):
            continue
        if inc_lower and not any(in_k in all_sms_content for in_k in inc_lower):
            continue
        filtered_numbers.append(item)
    return filtered_numbers


def freereceivesms_check_single_number(number_info, user_agent, service, base_url):
    """
    檢查單一號碼的函數，使用傳入的 Selenium Service 實例。
    """
    number_url = number_info['url']
    phone_number_text = number_info['number']
    options = create_adblocking_options(user_agent)
    
    driver = None
    result = None
    for i in range(2):
        try:
            print(f"    [THREAD] 檢查號碼: {phone_number_text} ...", end="", flush=True)
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)
            driver.get(number_url)
            message_row_selector = '.container .row.border-bottom'
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, message_row_selector)))
            time.sleep(4)
            num_soup = BeautifulSoup(driver.page_source, 'html.parser')
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
                sms_content_element = latest_row.select_one('.col-lg-8 div')
                sms_content = sms_content_element.get_text(strip=True) if sms_content_element else "無法讀取簡訊內容。"
                if time_text and is_within_last_hour(time_text):
                    if len(sms_content) > 80 and (sms_content.endswith('==') or sms_content.endswith('=')):
                        sms_content = " 【注意：內容可能被網站加密，請在瀏覽器中確認】"+sms_content
                    print(f"  -> \033[92m找到活躍號碼 (最新訊息: {time_text})\033[0m")
                    result = {'number': phone_number_text, 'url': number_url, 'last_sms': sms_content, 'smss': message_rows_contents}
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
        time.sleep(5)
    return result

def freereceivesms_find_active_numbers(CHROME_SERVICE, base_url, country_code=COUNTRY_CODE, page=PAGE_INDEX):
    """
    取得所有號碼列表，然後使用執行緒池併發檢查號碼。
    """
    print(f"[*] 正在使用 Selenium 搜尋 {country_code.upper()} 國碼的號碼...")
    numbers_to_check = []
    country_page_url = f"{base_url}/{country_code}/{page}/"
    print(f"[*] 目標國家頁面: {country_page_url}")
    driver = None
    try:
        options = create_adblocking_options(HEADERS["User-Agent"])
        print("[*] 正在載入國家頁面以取得號碼清單...")
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.set_page_load_timeout(30)
        driver.get(country_page_url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        number_boxes = soup.select('.number-boxes-item')
        if not number_boxes:
            print("[!] 在國家頁面上找不到任何號碼。網站結構可能已更改或載入失敗。 ")
            return []
        for box in number_boxes:
            link_tag = box.find('a', class_='btn-outline-info')
            if not link_tag or 'href' not in link_tag.attrs:
                continue
            number_path = link_tag['href']
            number_url = f"{base_url}{number_path}"
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
    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_number = {executor.submit(freereceivesms_check_single_number, num_info, HEADERS['User-Agent'], CHROME_SERVICE, base_url): num_info for num_info in numbers_to_check}
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    print(f"\n[*] 搜尋完畢。總共找到 {len(raw_active_numbers)} 個活躍號碼。")
    return raw_active_numbers

def receivesmss_check_single_number(number_info, user_agent, service, base_url):
    """
    使用 Selenium 檢查 receive-smss.com 的單一號碼。
    """
    number_url = number_info['url']
    phone_number_text = number_info['number']
    options = create_adblocking_options(user_agent)
    
    driver = None
    result = None
    try:
        print(f"    [THREAD] 檢查號碼: {phone_number_text} ...", end="", flush=True)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        driver.get(number_url)
        
        message_row_selector = 'div.row.border-bottom.py-2'
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, message_row_selector)))
        time.sleep(2) # 等待頁面可能存在的JS渲染

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        message_rows = soup.select(message_row_selector)
        
        if not message_rows:
            print("  -> 找不到訊息列。")
            return None

        latest_row = message_rows[0]
        time_element = latest_row.select_one('div.col-md-2.text-right span.text-muted')
        time_text = time_element.get_text(strip=True) if time_element else ""

        if time_text and is_within_last_hour(time_text):
            sms_content_element = latest_row.select_one('div.col-md-8')
            sms_content = sms_content_element.get_text(strip=True) if sms_content_element else "無法讀取簡訊內容。"
            all_smss = [row.select_one('div.col-md-8').get_text(strip=True) for row in message_rows if row.select_one('div.col-md-8')]

            print(f"  -> \033[92m找到活躍號碼 (最新訊息: {time_text})\033[0m")
            result = {'number': phone_number_text, 'url': number_url, 'last_sms': sms_content, 'smss': all_smss}
        else:
            print(f"  -> 不活躍 (最新訊息: {time_text})")
    except WebDriverException as e:
        print(f"  -> \033[91mSelenium 讀取失敗: {e}\033[0m")
    except Exception as e:
        print(f"  -> 檢查 {phone_number_text} 失敗: {e}")
    finally:
        if driver:
            driver.quit()
    return result

def receivesmss_find_active_numbers(CHROME_SERVICE, base_url, user_agent):
    """
    使用 Selenium 從 receive-smss.com 取得號碼列表。
    """
    print(f"[*] 正在使用 Selenium 搜尋 {base_url} 的號碼...")
    numbers_to_check = []
    driver = None
    try:
        options = create_adblocking_options(user_agent)
        
        print("[*] 正在載入主頁面以取得號碼清單...")
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.set_page_load_timeout(40)

        for attempt in range(3):
            try:
                driver.get(base_url)
                
                print("[*] 正在等待 Cloudflare 驗證...")
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".number-boxes > a"))
                )
                print("[*] Cloudflare 驗證通過，頁面已載入。")

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                number_links = soup.select('.number-boxes > a')

                if number_links:
                    print(f"[*] 第 {attempt + 1} 次嘗試成功找到號碼連結。")
                    for link in number_links:
                        number_path = link.get('href')
                        if number_path:
                            number_url = f"{base_url.rstrip('/')}{number_path}"
                            phone_number_tag = link.select_one('.number-boxes-itemm-number')
                            phone_number_text = phone_number_tag.get_text(strip=True) if phone_number_tag else "N/A"
                            numbers_to_check.append({'number': phone_number_text, 'url': number_url})
                    break
                else:
                    print(f"[!] 第 {attempt + 1} 次嘗試在主頁上找不到任何號碼。")
                    driver.refresh()
            except WebDriverException as e:
                print(f"\n[!] 第 {attempt + 1} 次嘗試載入主頁面或等待元素時發生錯誤: {e}")
                driver.refresh()

        if not numbers_to_check:
            print("[!] 在 3 次嘗試後，仍然無法在主頁上找到任何號碼。")
            return []

        print(f"[*] 成功找到 {len(numbers_to_check)} 個號碼，開始併發檢查...")

    except Exception as e:
        print(f"\n[!] 載入主頁面發生一般錯誤: {e}")
        return []
    finally:
        if driver:
            driver.quit()

    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_number = {executor.submit(receivesmss_check_single_number, num_info, user_agent, CHROME_SERVICE, base_url): num_info for num_info in numbers_to_check}
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    
    print(f"\n[*] 搜尋完畢。總共找到 {len(raw_active_numbers)} 個活躍號碼。")
    return raw_active_numbers

def tempnumber_check_single_number(number_info, user_agent, service, base_url):
    """
    使用 Selenium 檢查 temp-number.com 的單一號碼。
    """
    number_url = number_info['url']
    phone_number_text = number_info['number']
    options = create_adblocking_options(user_agent)
    
    driver = None
    result = None
    try:
        print(f"    [THREAD] 檢查號碼 (Temp-Number): {phone_number_text} ...", end="", flush=True)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        driver.get(number_url)
        
        message_row_selector = 'div.direct-chat-msg'
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, message_row_selector)))
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        message_rows = soup.select(message_row_selector)
        
        if not message_rows:
            print("  -> 找不到訊息列。")
            return None

        latest_row = message_rows[0]
        time_element = latest_row.select_one('time.direct-chat-timestamp')
        time_text = time_element.get_text(strip=True) if time_element else ""

        if time_text and is_within_last_hour(time_text):
            sms_content_element = latest_row.select_one('div.direct-chat-text')
            sms_content = sms_content_element.get_text(strip=True) if sms_content_element else "無法讀取簡訊內容。"
            
            all_smss = [row.select_one('div.direct-chat-text').get_text(strip=True) for row in message_rows if row.select_one('div.direct-chat-text')]

            print(f"  -> \033[92m找到活躍號碼 (最新訊息: {time_text})\033[0m")
            result = {'number': phone_number_text, 'url': number_url, 'last_sms': sms_content, 'smss': all_smss}
        else:
            print(f"  -> 不活躍 (最新訊息: {time_text})")
            
    except WebDriverException as e:
        print(f"  -> Selenium 讀取時發生超時或錯誤: {str(e).splitlines()[0]}")
    except Exception as e:
        print(f"  -> 檢查 {phone_number_text} 失敗: {e}")
    finally:
        if driver:
            driver.quit()
    return result

def tempnumber_find_active_numbers(CHROME_SERVICE, base_url, user_agent):
    """
    使用 Selenium 從 temp-number.com 取得號碼列表。
    """
    print(f"[*] 正在使用 Selenium 搜尋 {base_url} 的號碼...")
    numbers_to_check = []
    driver = None
    # 特化 URL 結構
    country_url = f"{base_url.rstrip('/')}/countries/United-States"
    print(f"[*] 目標國家頁面 (Temp-Number): {country_url}")

    try:
        options = create_adblocking_options(user_agent)
        
        print("[*] 正在載入國家頁面以取得號碼清單 (temp-number.com)...")
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.set_page_load_timeout(60)
        driver.get(country_url)

        print("[*] 正在等待 temp-number.com 頁面載入...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.country-link"))
        )
        print("[*] 頁面載入完畢，開始解析號碼...")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        number_links = soup.select("a.country-link")
        
        if not number_links:
            print("[!] 在 temp-number.com 上找不到任何號碼連結。")
            return []

        for link in number_links:
            number_path = link.get('href')
            if number_path:
                number_url = f"{base_url.rstrip('/')}{number_path}"
                phone_number_text_tag = link.find("h4")
                phone_number_text = phone_number_text_tag.get_text(strip=True) if phone_number_text_tag else "N/A"
                if phone_number_text and not phone_number_text.startswith('+'):
                    phone_number_text = '+' + phone_number_text
                
                if phone_number_text.startswith('+'):
                    numbers_to_check.append({'number': phone_number_text, 'url': number_url})

        print(f"[*] 成功找到 {len(numbers_to_check)} 個號碼，開始併發檢查...")

    except Exception as e:
        print(f"\n[!] 載入 temp-number.com 主頁面或等待元素時發生錯誤: {e}")
        if driver:
            debug_path = "temp_number_debug.html"
            print(f"\n--- 正在將頁面原始碼寫入 {debug_path} (偵錯用) ---")
            try:
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"--- 寫入完成 --- ")
            except Exception as write_e:
                print(f"--- 寫入偵錯檔案時發生錯誤: {write_e} ---")
        return []
    finally:
        if driver:
            driver.quit()

    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_number = {executor.submit(tempnumber_check_single_number, num_info, user_agent, CHROME_SERVICE, base_url): num_info for num_info in numbers_to_check}
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    
    print(f"\n[*] temp-number.com 搜尋完畢。總共找到 {len(raw_active_numbers)} 個活躍號碼。")
    return raw_active_numbers

def scrape_all_sites(CHROME_SERVICE, target_urls):
    """
    遍歷 target_urls 列表，並為每個 URL 呼叫對應的爬蟲函式。
    """
    country_code = config.get('general', {}).get('country_code', 'us')
    page_index = config.get('general', {}).get('page_index', 1)
    user_agent = config.get('headers', {}).get('User-Agent', 'Mozilla/5.0')

    all_results = []
    print(f"[*] 開始遍歷 {len(target_urls)} 個目標網站...")

    for url in target_urls:
        print(f"\n--- 正在處理網站: {url} ---")
        result_key = url.split('.')[1] if '.' in url else url
        
        if "freereceivesms" in url:
            try:
                numbers = freereceivesms_find_active_numbers(CHROME_SERVICE, base_url=url, country_code=country_code, page=page_index)
                if numbers:
                    for number in numbers:
                        number['source'] = 'Free-Receive-Sms'
                    all_results.extend(numbers)
            except Exception as e:
                print(f"[!] 處理 {url} 時發生錯誤: {e}")
        elif "receive-smss" in url:
            try:
                numbers = receivesmss_find_active_numbers(CHROME_SERVICE, base_url=url, user_agent=user_agent)
                if numbers:
                    for number in numbers:
                        number['source'] = 'Receive-Sms'
                    all_results.extend(numbers)
            except Exception as e:
                print(f"[!] 處理 {url} 時發生錯誤: {e}")
        elif "temp-number" in url:
            try:
                numbers = tempnumber_find_active_numbers(CHROME_SERVICE, base_url=url, user_agent=user_agent)
                if numbers:
                    for number in numbers:
                        number['source'] = 'Temp-Number'
                    all_results.extend(numbers)
            except Exception as e:
                print(f"[!] 處理 {url} 時發生錯誤: {e}")
        else:
            print(f"[!] 警告：找不到為 {url} 設定的解析器。 ")

    print(f"\n[*] 所有網站處理完畢，總共從 {len(target_urls)} 個網站中收集到 {len(all_results)} 個活躍號碼。 ")
    return all_results