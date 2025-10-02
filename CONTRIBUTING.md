# **🤝 貢獻指南 (Contributing Guide)**

感謝您對「臨時簡訊接收號碼監控器」專案的興趣！您的貢獻對於提升爬蟲的穩定性和功能擴展至關重要。

Thank you for your interest in the Temporary SMS Receiver Monitor project\! Your contributions are vital to enhancing the stability and expanding the features of this scraper.

## **如何開始 (Getting Started)**

### **1\. 設置環境 (Setup Environment)**

請確保您已安裝所有依賴項：

Please ensure you have installed all dependencies:

`uv sync`

### **2\. 報告錯誤 (Reporting Bugs)**

如果您發現任何錯誤，例如爬蟲失敗、網站結構變更導致解析錯誤，或是簡訊內容仍被加密，請透過 Issue 追蹤器報告。

If you encounter any bugs, such as scraping failures, parsing errors due to website structure changes, or SMS content remaining encrypted, please report them via the Issue tracker.

### **3\. 提交變更 (Submitting Changes)**

我們主要接受功能新增、錯誤修復和爬蟲穩定性增強的 Pull Request (PR)。

We primarily accept Pull Requests (PRs) for new features, bug fixes, and scraper stability improvements.

* 請先 **Fork** 本專案。 (Fork the repository first.)  
* 為您的變更創建一個新的分支。 (Create a new branch for your changes.)  
* 確保您的程式碼遵循 PEP 8 規範，並在提交前運行測試 (如果適用)。 (Ensure your code follows PEP 8 and run tests before committing.)  
* 提交 PR 時，請清楚說明您做了哪些變更以及解決了什麼問題。 (Clearly describe your changes and what issue they resolve in your PR.)

### **4\. 執行測試 (Running Tests)**

本專案包含一套自動化測試，以確保程式碼品質和功能穩定。在您提交變更前，請務必在本地端運行測試。

This project includes an automated test suite to ensure code quality and stability. Before submitting your changes, please make sure to run the tests locally.

1.  **安裝測試依賴 (Install Testing Dependencies)**

    測試工具並未包含在主要的 `uv sync` 中。請使用以下指令單獨安裝它們：
    
    The testing tools are not included in the main `uv sync`. Please install them separately using the following command:

    ```bash
    uv pip install pytest pytest-mock
    ```

2.  **運行測試套件 (Run the Test Suite)**

    使用 `pytest` 模組來執行所有測試。在 Windows 環境下，為了避免路徑問題並確保使用虛擬環境中的正確 Python 版本，建議使用以下完整指令：

    Use the `pytest` module to run all tests. On Windows, it is recommended to use the full command below to avoid path issues and ensure the correct Python version from the virtual environment is used:

    ```bash
    # 在專案根目錄下執行 (Run from the project root directory)
    .venv\Scripts\python.exe -m pytest -v
    ```

    如果您看到 `18 passed` (或更多) 且沒有 `failed` 或 `errors` 的訊息，代表所有測試都已成功通過。

    If you see `18 passed` (or more) with no `failed` or `errors`, it means all tests have passed successfully.

## **💻 專案結構建議 (Suggested Project Structure)**

我們目前將本地和 Colab 啟動程式碼分開，但核心爬蟲邏輯是共享的。

We currently separate local and Colab startup code, but the core scraping logic is shared.

* **main.py**: 本地執行啟動邏輯 (Local execution startup logic)   
* **scraper\_core.py**: 將 is\_within\_last\_hour, check\_single\_number, find\_active\_numbers 移至此處，以減少程式碼重複。 (Move core functions here to reduce duplication.)  
* **config.toml**: 網站設定和爬蟲參數 (Website configurations and scraper parameters)

## **✨ 未來功能願景 (Future Feature Vision)**

以下是我們對專案的未來規劃，歡迎認領開發！

Here is our roadmap for future development. Feel free to claim and contribute to any of these ideas\!

### **核心擴展 (Core Extensions)**

* **容納更多網站 (Multiple Site Support)**  
  * **願景:** 建立一個可配置的模組，允許用戶在 config.toml 中新增多個臨時簡訊網站的爬蟲配置（CSS 選擇器、URL 格式等）。  
  * **Vision:** Create a configurable module allowing users to add scraping configurations (CSS selectors, URL formats, etc.) for multiple temporary SMS websites in config.toml.  
* **號碼使用紀錄與黑名單 (Usage History & Blacklisting)**  
  * **願景:** 在前端新增一個介面，允許用戶勾選「**是否使用過**」或「**標記無效**」某個號碼。爬蟲在下次執行時將避免檢查或優先檢查未使用的號碼。  
  * **Vision:** Add a frontend interface to let users check/uncheck **"Used"** or **"Mark Invalid"** for specific numbers. The scraper will then avoid or prioritize these numbers in future runs.

### **新增 7 個有趣或實用的功能 (7 New Exciting Features)**

1. **動態國家/頁面切換 (Dynamic Country/Page Switching)**  
   * **說明:** 在網頁介面上加入國家代碼（如 US, CA, GB）和頁碼的下拉選單或按鈕，允許使用者即時切換要監控的國家或頁面，無需重新啟動程式。  
2. **通知整合 (Notification Integration)**  
   * **說明:** 支援透過簡單 Webhook（例如 Telegram, Discord）發送通知。當爬蟲找到一個在設定時間內（如 5 分鐘）有新訊息的活躍號碼時，自動發送通知提醒使用者。  
3. **爬蟲健康監測儀表板 (Scraper Health Dashboard)**  
   * **說明:** 在 Flask 頁面新增一個簡單的儀表板，顯示每個爬取網站的**成功率**、**上次失敗時間**和**平均檢查延遲**，幫助使用者判斷哪個網站最穩定。  
4. **基於關鍵字篩選 (Keyword Filtering)**  
   * **說明:** 允許使用者在 config.toml 或網頁介面中設定一組關鍵字（如 '驗證碼', 'OTP', 'Code'）。只有包含這些關鍵字的簡訊才會在結果頁面中顯示。  
5. **自動化 Base64 解密嘗試 (Automated Base64 Decryption Attempt)**  
   * **說明:** 針對加密內容（如您遇到的 Base64 字串），增加 Python 內建的 Base64 解碼嘗試。如果解碼成功且結果是可讀文字，則顯示解碼後的內容。  
6. **彈性時間解析器 (Flexible Time Parser)**  
   * **說明:** 增強 is\_within\_last\_hour 函數，使其能夠識別更多語言（如西班牙文、法文）和更多時間格式（如 "Just now", "Hace 3 minutos"），提高國際化支援。  
7. **Docker 部署支援 (Docker Deployment Support)**  
   * **說明:** 提供 Dockerfile 和相關說明文件，讓使用者可以輕鬆地將應用程式容器化，簡化環境設置和部署流程，特別是在雲端環境中。

## **❓ 有疑問嗎？ (Questions?)**

如果您對貢獻過程或任何功能有疑問，請隨時在 Issue 追蹤器中提問。

If you have any questions about the contribution process or any features, please feel free to ask in the Issue tracker.

**期待您的貢獻！(Happy Contributing\!)**