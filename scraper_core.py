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

def setup_adblocker(lang_dict):
    """
    檢查、下載並解壓縮 uBlock Origin 廣告攔截外掛。
    """
    if os.path.isdir(EXTENSION_PATH):
        return
    
    print(lang_dict['ADBLOCK_MISSING'])
    try:
        r = requests.get(UBLOCK_URL, stream=True)
        r.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            os.makedirs(EXTENSION_PATH, exist_ok=True)
            z.extractall(EXTENSION_PATH)
        print(lang_dict['ADBLOCK_INSTALLED'].format(path=EXTENSION_PATH))
        
    except requests.exceptions.RequestException as e:
        print(lang_dict['ADBLOCK_DOWNLOAD_FAIL'].format(e=e))
    except zipfile.BadZipFile:
        print(lang_dict['ADBLOCK_BAD_ZIP'])
    except Exception as e:
        print(lang_dict['ADBLOCK_UNKNOWN_ERROR'].format(e=e))

def create_adblocking_options(user_agent, lang_dict):
    """
    建立並回傳一個已載入廣告攔截外掛的 ChromeOptions 物件。
    """
    setup_adblocker(lang_dict)
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'user-agent={user_agent}')
    
    if os.path.isdir(EXTENSION_PATH):
        options.add_argument(f'--load-extension={EXTENSION_PATH}')
    else:
        print(lang_dict['ADBLOCK_LOAD_WARN'])
        
    return options

def is_within_last_hour(time_text):
    """
    檢查時間文字 (例如 '5分钟前', '2小时前') 是否在最近一小時內。
    """
    time_text = time_text.strip()
    if any(s in time_text for s in ['分钟前', '分鐘前', 'minutes ago','秒前','seconds ago']):
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


def freereceivesms_check_single_number(number_info, user_agent, service, base_url, lang_dict):
    """
    檢查單一號碼的函數，使用傳入的 Selenium Service 實例。
    """
    number_url = number_info['url']
    phone_number_text = number_info['number']
    options = create_adblocking_options(user_agent, lang_dict)
    
    driver = None
    result = None
    for i in range(2):
        try:
            print(lang_dict['CHECKING_NUMBER'].format(number=phone_number_text), end="", flush=True)
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
                     message_rows_contents.append(item_element.get_text(strip=True) if item_element else lang_dict['CANNOT_READ_SMS'])
                time_text = ''
                if time_element_lg:
                    time_text = time_element_lg.get_text(strip=True)
                elif time_element_sm:
                    time_text = time_element_sm.get_text(strip=True)
                sms_content_element = latest_row.select_one('.col-lg-8 div')
                sms_content = sms_content_element.get_text(strip=True) if sms_content_element else lang_dict['CANNOT_READ_SMS']
                if time_text and is_within_last_hour(time_text):
                    if len(sms_content) > 80 and (sms_content.endswith('==') or sms_content.endswith('=')):
                        sms_content = lang_dict['SMS_CONTENT_ENCRYPTED'] + sms_content
                    print(lang_dict['FOUND_ACTIVE_NUMBER'].format(time=time_text))
                    result = {'number': phone_number_text, 'url': number_url, 'last_sms': sms_content, 'smss': message_rows_contents, 'last_time':time_text}
                else:
                    print(lang_dict['INACTIVE_NUMBER'].format(time=time_text))
            else:
                print(lang_dict['NO_MESSAGE_ROWS'])
        except WebDriverException as e:
            print(lang_dict['SELENIUM_READ_FAIL'].format(e=e))
        except Exception as e:
            print(lang_dict['CHECK_NUMBER_FAIL'].format(number=phone_number_text, e=e))
        finally:
            if driver:
                driver.quit()
        time.sleep(5)
    return result

def freereceivesms_find_active_numbers(CHROME_SERVICE, base_url, lang_dict, country_code=COUNTRY_CODE, page=PAGE_INDEX):
    """
    取得所有號碼列表，然後使用執行緒池併發檢查號碼。
    """
    print(lang_dict['SEARCHING_NUMBERS_SELENIUM'].format(country=country_code.upper()))
    numbers_to_check = []
    country_page_url = f"{base_url}/{country_code}/{page}/"
    print(lang_dict['TARGET_COUNTRY_PAGE'].format(url=country_page_url))
    driver = None
    try:
        options = create_adblocking_options(HEADERS["User-Agent"], lang_dict)
        print(lang_dict['LOADING_COUNTRY_PAGE'])
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.set_page_load_timeout(30)
        driver.get(country_page_url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        number_boxes = soup.select('.number-boxes-item')
        if not number_boxes:
            print(lang_dict['NO_NUMBERS_FOUND_ON_PAGE'])
            return []
        for box in number_boxes:
            link_tag = box.find('a', class_='btn-outline-info')
            if not link_tag or 'href' not in link_tag.attrs:
                continue
            number_path = link_tag['href']
            number_url = f"{base_url}{number_path}"
            phone_number_text = box.find('h4').get_text(strip=True) if box.find('h4') else "N/A"
            numbers_to_check.append({'number': phone_number_text, 'url': number_url})
        print(lang_dict['FOUND_NUMBERS_CONCURRENT_CHECK'].format(count=len(numbers_to_check)))
    except WebDriverException as e:
        print(lang_dict['LOAD_COUNTRY_PAGE_FAIL'].format(e=e))
        return None
    except Exception as e:
        print(lang_dict['LOAD_COUNTRY_PAGE_GENERAL_ERROR'].format(e=e))
        return None
    finally:
        if driver:
            driver.quit()
    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_number = {executor.submit(freereceivesms_check_single_number, num_info, HEADERS['User-Agent'], CHROME_SERVICE, base_url, lang_dict): num_info for num_info in numbers_to_check}
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    print(lang_dict['SEARCH_COMPLETE'].format(count=len(raw_active_numbers)))
    return raw_active_numbers

def receivesmss_check_single_number(number_info, user_agent, service, base_url, lang_dict):
    """
    使用 Selenium 檢查 receive-smss.com 的單一號碼。
    """
    number_url = number_info['url']
    phone_number_text = number_info['number']
    options = create_adblocking_options(user_agent, lang_dict)
    
    driver = None
    result = None
    try:
        print(lang_dict['CHECKING_NUMBER'].format(number=phone_number_text), end="", flush=True)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        driver.get(number_url)
        
        message_row_selector = 'div.row.border-bottom.py-2'
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, message_row_selector)))
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        message_rows = soup.select(message_row_selector)
        
        if not message_rows:
            print(lang_dict['NO_MESSAGE_ROWS'])
            return None

        latest_row = message_rows[0]
        time_element = latest_row.select_one('div.col-md-2.text-right span.text-muted')
        time_text = time_element.get_text(strip=True) if time_element else ""

        if time_text and is_within_last_hour(time_text):
            sms_content_element = latest_row.select_one('div.col-md-8')
            sms_content = sms_content_element.get_text(strip=True) if sms_content_element else lang_dict['CANNOT_READ_SMS']
            all_smss = [row.select_one('div.col-md-8').get_text(strip=True) for row in message_rows if row.select_one('div.col-md-8')]

            print(lang_dict['FOUND_ACTIVE_NUMBER'].format(time=time_text))
            result = {'number': phone_number_text, 'url': number_url, 'last_sms': sms_content, 'smss': all_smss, 'last_time':time_text}
        else:
            print(lang_dict['INACTIVE_NUMBER'].format(time=time_text))
    except WebDriverException as e:
        print(lang_dict['SELENIUM_READ_FAIL'].format(e=e))
    except Exception as e:
        print(lang_dict['CHECK_NUMBER_FAIL'].format(number=phone_number_text, e=e))
    finally:
        if driver:
            driver.quit()
    return result

def receivesmss_find_active_numbers(CHROME_SERVICE, base_url, user_agent, lang_dict):
    """
    使用 Selenium 從 receive-smss.com 取得號碼列表。
    """
    print(lang_dict['SEARCHING_NUMBERS_BASE_URL'].format(url=base_url))
    numbers_to_check = []
    driver = None
    try:
        options = create_adblocking_options(user_agent, lang_dict)
        
        print(lang_dict['LOADING_COUNTRY_PAGE'])
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.set_page_load_timeout(40)

        for attempt in range(3):
            try:
                driver.get(base_url)
                
                print(lang_dict['WAITING_CLOUDFLARE'])
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".number-boxes > a"))
                )
                print(lang_dict['CLOUDFLARE_PASS'])

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                number_links = soup.select('.number-boxes > a')

                if number_links:
                    print(lang_dict['FOUND_LINK_SUCCESS'].format(attempt=attempt + 1))
                    for link in number_links:
                        number_path = link.get('href')
                        if number_path:
                            number_url = f"{base_url.rstrip('/')}{number_path}"
                            phone_number_tag = link.select_one('.number-boxes-itemm-number')
                            phone_number_text = phone_number_tag.get_text(strip=True) if phone_number_tag else "N/A"
                            numbers_to_check.append({'number': phone_number_text, 'url': number_url})
                    break
                else:
                    print(lang_dict['NO_LINK_ON_ATTEMPT'].format(attempt=attempt + 1))
                    driver.refresh()
            except WebDriverException as e:
                print(lang_dict['LOAD_MAIN_PAGE_ATTEMPT_FAIL'].format(attempt=attempt + 1, e=e))
                driver.refresh()

        if not numbers_to_check:
            print(lang_dict['NO_NUMBERS_AFTER_RETRIES'])
            return []

        print(lang_dict['FOUND_NUMBERS_CONCURRENT_CHECK'].format(count=len(numbers_to_check)))

    except Exception as e:
        print(lang_dict['LOAD_MAIN_PAGE_GENERAL_ERROR'].format(e=e))
        return []
    finally:
        if driver:
            driver.quit()

    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_number = {executor.submit(receivesmss_check_single_number, num_info, user_agent, CHROME_SERVICE, base_url, lang_dict): num_info for num_info in numbers_to_check}
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    
    print(lang_dict['SEARCH_COMPLETE'].format(count=len(raw_active_numbers)))
    return raw_active_numbers

def tempnumber_check_single_number(number_info, user_agent, service, base_url, lang_dict):
    """
    使用 Selenium 檢查 temp-number.com 的單一號碼。
    """
    number_url = number_info['url']
    phone_number_text = number_info['number']
    options = create_adblocking_options(user_agent, lang_dict)
    
    driver = None
    result = None
    try:
        print(lang_dict['CHECKING_NUMBER_TEMP'].format(number=phone_number_text), end="", flush=True)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        driver.get(number_url)
        
        message_row_selector = 'div.direct-chat-msg'
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, message_row_selector)))
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        message_rows = soup.select(message_row_selector)
        
        if not message_rows:
            print(lang_dict['NO_MESSAGE_ROWS'])
            return None

        latest_row = message_rows[0]
        time_element = latest_row.select_one('time.direct-chat-timestamp')
        time_text = time_element.get_text(strip=True) if time_element else ""

        if time_text and is_within_last_hour(time_text):
            sms_content_element = latest_row.select_one('div.direct-chat-text')
            sms_content = sms_content_element.get_text(strip=True) if sms_content_element else lang_dict['CANNOT_READ_SMS']
            
            all_smss = [row.select_one('div.direct-chat-text').get_text(strip=True) for row in message_rows if row.select_one('div.direct-chat-text')]

            print(lang_dict['FOUND_ACTIVE_NUMBER'].format(time=time_text))
            result = {'number': phone_number_text, 'url': number_url, 'last_sms': sms_content, 'smss': all_smss, 'last_time':time_text}
        else:
            print(lang_dict['INACTIVE_NUMBER'].format(time=time_text))
            
    except WebDriverException as e:
        print(lang_dict['SELENIUM_TIMEOUT_ERROR'].format(e=str(e).splitlines()[0]))
    except Exception as e:
        print(lang_dict['CHECK_NUMBER_FAIL'].format(number=phone_number_text, e=e))
    finally:
        if driver:
            driver.quit()
    return result

def tempnumber_find_active_numbers(CHROME_SERVICE, base_url, user_agent, lang_dict):
    """
    使用 Selenium 從 temp-number.com 取得號碼列表。
    """
    print(lang_dict['SEARCHING_NUMBERS_BASE_URL'].format(url=base_url))
    numbers_to_check = []
    driver = None
    country_url = f"{base_url.rstrip('/')}/countries/United-States"
    print(lang_dict['TARGET_COUNTRY_PAGE_TEMP'].format(url=country_url))

    try:
        options = create_adblocking_options(user_agent, lang_dict)
        
        print(lang_dict['LOADING_COUNTRY_PAGE_TEMP'])
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.set_page_load_timeout(60)
        driver.get(country_url)

        print(lang_dict['WAITING_PAGE_LOAD_TEMP'])
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.country-link"))
        )
        print(lang_dict['PAGE_LOADED_PARSING'])
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        number_links = soup.select("a.country-link")
        
        if not number_links:
            print(lang_dict['NO_NUMBERS_FOUND_ON_PAGE_TEMP'])
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

        print(lang_dict['FOUND_NUMBERS_CONCURRENT_CHECK'].format(count=len(numbers_to_check)))

    except Exception as e:
        print(lang_dict['LOAD_MAIN_PAGE_GENERAL_ERROR_TEMP'].format(e=e))
        if driver:
            debug_path = "temp_number_debug.html"
            print(lang_dict['WRITING_DEBUG_FILE'].format(path=debug_path))
            try:
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(lang_dict['WRITE_DEBUG_FILE_DONE'])
            except Exception as write_e:
                print(lang_dict['WRITE_DEBUG_FILE_ERROR'].format(e=write_e))
        return []
    finally:
        if driver:
            driver.quit()

    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_number = {executor.submit(tempnumber_check_single_number, num_info, user_agent, CHROME_SERVICE, base_url, lang_dict): num_info for num_info in numbers_to_check}
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    
    print(lang_dict['SEARCH_COMPLETE_TEMP'].format(count=len(raw_active_numbers)))
    return raw_active_numbers

def scrape_all_sites(CHROME_SERVICE, target_urls, lang_dict):
    """
    遍歷 target_urls 列表，並為每個 URL 呼叫對應的爬蟲函式。
    """
    country_code = config.get('general', {}).get('country_code', 'us')
    page_index = config.get('general', {}).get('page_index', 1)
    user_agent = config.get('headers', {}).get('User-Agent', 'Mozilla/5.0')

    all_results = []
    print(lang_dict['TRAVERSING_SITES_START'].format(count=len(target_urls)))

    for url in target_urls:
        print(lang_dict['PROCESSING_SITE'].format(url=url))
        
        if "freereceivesms" in url:
            try:
                numbers = freereceivesms_find_active_numbers(CHROME_SERVICE, base_url=url, lang_dict=lang_dict, country_code=country_code, page=page_index)
                if numbers:
                    for number in numbers:
                        number['source'] = 'Free-Receive-Sms'
                    all_results.extend(numbers)
            except Exception as e:
                print(lang_dict['PROCESS_SITE_ERROR'].format(url=url, e=e))
        elif "receive-smss" in url:
            try:
                numbers = receivesmss_find_active_numbers(CHROME_SERVICE, base_url=url, user_agent=user_agent, lang_dict=lang_dict)
                if numbers:
                    for number in numbers:
                        number['source'] = 'Receive-Smss'
                    all_results.extend(numbers)
            except Exception as e:
                print(lang_dict['PROCESS_SITE_ERROR'].format(url=url, e=e))
        elif "temp-number" in url:
            try:
                numbers = tempnumber_find_active_numbers(CHROME_SERVICE, base_url=url, user_agent=user_agent, lang_dict=lang_dict)
                if numbers:
                    for number in numbers:
                        number['source'] = 'Temp-Number'
                    all_results.extend(numbers)
            except Exception as e:
                print(lang_dict['PROCESS_SITE_ERROR'].format(url=url, e=e))
        else:
            print(lang_dict['PARSER_NOT_FOUND'].format(url=url))

    print(lang_dict['ALL_SITES_DONE'].format(count=len(target_urls), total=len(all_results)))
    return all_results