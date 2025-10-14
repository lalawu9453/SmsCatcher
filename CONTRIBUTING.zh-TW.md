# **🤝 貢獻指南**

[**English**](./CONTRIBUTING.md) • **繁體中文**

---

感謝您對「臨時簡訊接收號碼監控器」專案的興趣！您的貢獻對於提升爬蟲的穩定性和功能擴展至關重要。

## **如何開始**

### **1. 設置環境**

請確保您已安裝所有依賴項：

```bash
uv sync
```

### **2. 報告錯誤**

如果您發現任何錯誤，例如爬蟲失敗、網站結構變更導致解析錯誤，或是簡訊內容仍被加密，請透過 [Issue 追蹤器](https://github.com/LayorX/Temporary-SMS-Receiver-Monitor/issues) 報告。

### **3. 提交變更**

我們主要接受功能新增、錯誤修復和爬蟲穩定性增強的 Pull Request (PR)。

*   請先 **Fork** 本專案。
*   為您的變更創建一個新的分支。
*   確保您的程式碼遵循 PEP 8 規範，並在提交前運行測試。
*   提交 PR 時，請清楚說明您做了哪些變更以及解決了什麼問題。

---

## **🧪 執行測試**

本專案包含一套自動化測試，以確保程式碼品質和功能穩定。在您提交變更前，請務必在本地端運行測試。

### **1. 安裝測試依賴**

測試工具並未包含在主要的 `uv sync` 中。請使用以下指令單獨安裝它們：

```bash
uv pip install pytest pytest-mock
```

### **2. 運行測試套件**

使用 `pytest` 模組來執行所有測試。在 Windows 環境下，為了避免路徑問題並確保使用虛擬環境中的正確 Python 版本，建議使用以下完整指令：

```bash
# 在專案根目錄下執行
.venv\Scripts\python.exe -m pytest -v
```

*   **單元測試 (Unit Tests)**：這些測試位於 `tests/test_scraper_core.py`，主要驗證 `is_within_last_hour` 等輔助函式的邏輯正確性。
*   **煙霧測試 (Smoke Tests)**：此類測試（例如 `test_tempnumber_scraper_smoke_test`）會實際執行爬蟲的主要函式，但只驗證其是否能順利完成並回傳正確的資料類型（如 `list`），而不檢查具體內容。這有助於在重構後快速捕捉到致命的執行錯誤。

如果您看到所有測試項目都顯示 `PASSED` 且沒有 `FAILED` 或 `ERRORS` 的訊息，代表所有測試都已成功通過。

### **3. 測試應用程式啟動參數**

若要測試 `main.py` 的命令列啟動參數，請直接執行主程式並帶上 `--help` 參數來查看所有選項：

```bash
uv run python main.py --help
```

---

## **✍️ 新增爬蟲撰寫框架**

想要整合一個新的簡訊網站嗎？請遵循以下步驟，這將幫助您快速、標準化地完成工作。

### **步驟 1：網站初步分析**

1.  **打開目標網站**：在您的瀏覽器中打開想要爬取的網站。
2.  **使用開發者工具**：按下 `F12` 打開開發者工具，選擇「Elements」分頁。
3.  **觀察網站行為**：
    *   **內容載入方式**：號碼列表是靜態載入（原始碼中可見）還是動態載入（由 JavaScript 產生）？本專案預設使用 `Selenium`，因此兩者皆可處理。
    *   **人機驗證**：網站是否有 Cloudflare 保護或 Google reCAPTCHA？這會增加爬取難度，`Selenium` 的長等待時間設定有助於通過部分驗證。
    *   **廣告干擾**：網站是否有大量彈出式廣告或覆蓋型廣告？我們的 `create_adblocking_options` 函式可以有效應對此問題。

### **步驟 2：尋找關鍵 CSS 選取器**

這是最關鍵的一步。您需要為新網站找到一組穩定的 CSS 選取器。使用開發者工具的「Inspect」（左上角的小箭頭圖示）來點擊頁面元素，並在「Elements」面板中找到它們。

**您需要記錄以下選取器：**

1.  **在號碼列表頁面:**
    *   `number_links_selector`: 指向**每一個**包含號碼連結的容器元素。 (例如：`a.country-link`)
    *   `phone_number_text_selector`: 在上述容器中，指向顯示電話號碼文字的元素。 (例如：`h4`)

2.  **在單一號碼的訊息頁面:**
    *   `message_rows_selector`: 指向**每一則**訊息的容器元素。 (例如：`div.direct-chat-msg`)
    *   `time_selector`: 在訊息容器中，指向顯示時間戳的元素。 (例如：`time.direct-chat-timestamp`)
    *   `content_selector`: 在訊息容器中，指向顯示簡訊內容的元素。 (例如：`div.direct-chat-text`)

### **步驟 3：撰寫爬蟲程式碼**

在 `scraper_core.py` 中，您需要建立兩個函式：

1.  **`[sitename]_find_active_numbers(...)`**: 用於從號碼列表頁面抓取所有號碼，並併發檢查它們。
2.  **`[sitename]_check_single_number(...)`**: 用於檢查單一號碼頁面，判斷其是否活躍並抓取簡訊。

**程式碼框架範本：**

```python
# 函式 1: 尋找活躍號碼
def [sitename]_find_active_numbers(CHROME_SERVICE, base_url, user_agent):
    print(f"[*] 正在使用 Selenium 搜尋 {base_url} 的號碼...")
    numbers_to_check = []
    driver = None
    try:
        # 1. 務必使用廣告攔截器
        options = create_adblocking_options(user_agent)
        driver = webdriver.Chrome(service=CHROME_SERVICE, options=options)
        driver.get(base_url) # 或特定的國家頁面 URL

        # 2. 等待號碼列表載入
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[number_links_selector]")))
        time.sleep(3)

        # 3. 使用 BeautifulSoup 解析頁面
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        number_links = soup.select("[number_links_selector]")

        # 4. 遍歷連結，建立待檢查的號碼資訊
        for link in number_links:
            # ... 根據您找到的選取器解析出號碼和 URL ...
            numbers_to_check.append({'number': phone_number_text, 'url': number_url})

    finally:
        if driver:
            driver.quit()

    # 5. 使用執行緒池併發檢查
    raw_active_numbers = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 將 [sitename]_check_single_number 傳入
        future_to_number = {executor.submit([sitename]_check_single_number, num_info, user_agent, CHROME_SERVICE, base_url): num_info for num_info in numbers_to_check}
        for future in as_completed(future_to_number):
            result = future.result()
            if result:
                raw_active_numbers.append(result)
    return raw_active_numbers

# 函式 2: 檢查單一號碼
def [sitename]_check_single_number(number_info, user_agent, service, base_url):
    # ... (省略 try/except/finally 結構) ...
    driver = webdriver.Chrome(service=service, options=create_adblocking_options(user_agent))
    driver.get(number_info['url'])

    # 1. 等待訊息列表載入
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[message_rows_selector]")))
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    message_rows = soup.select("[message_rows_selector]")

    # 2. 解析最新一則訊息的時間
    latest_row = message_rows[0]
    time_element = latest_row.select_one("[time_selector]")
    time_text = time_element.get_text(strip=True)

    # 3. 判斷是否活躍，如果活躍則打包回傳結果
    if time_text and is_within_last_hour(time_text):
        sms_content = latest_row.select_one("[content_selector]").get_text(strip=True)
        all_smss = [row.select_one("[content_selector]").get_text(strip=True) for row in message_rows]
        
        # 4. 必須回傳此標準格式的字典
        return {'number': number_info['number'], 'url': number_info['url'], 'last_sms': sms_content, 'smss': all_smss}
    # ... (省略其餘邏輯)
```

### **步驟 4：整合到核心**

1.  打開 `scraper_core.py`。
2.  找到 `scrape_all_sites` 函式。
3.  在 `for url in target_urls:` 迴圈中，新增一個 `elif` 區塊來處理您的新網站。

    ```python
    elif "[sitename]" in url: # 使用新網站的獨特網域名稱
        try:
            numbers = [sitename]_find_active_numbers(CHROME_SERVICE, base_url=url, user_agent=user_agent)
            if numbers:
                for number in numbers:
                    # ！！！重要：為您的結果打上來源標籤
                    number['source'] = '[SiteName]' # 例如：'MyNewSite'
                all_results.extend(numbers)
        except Exception as e:
            print(f"[!] 處理 {url} 時發生錯誤: {e}")
    ```

### **步驟 5：偵錯與測試**

1.  **偵錯**：如果在解析時遇到困難或 `UnicodeEncodeError`，請使用以下技巧將頁面原始碼寫入檔案進行分析：
    ```python
    with open("debug.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    ```
2.  **新增測試**：在 `tests/test_scraper_core.py` 中為您的新爬蟲新增一個煙霧測試，以確保它能穩定運行。複製 `test_tempnumber_scraper_smoke_test` 的結構並替換為您的函式即可。

---

## **❓ 有疑問嗎？**

如果您對貢獻過程或任何功能有疑問，請隨時在 [Issue 追蹤器](https://github.com/LayorX/Temporary-SMS-Receiver-Monitor/issues) 中提問。

**期待您的貢獻！**
