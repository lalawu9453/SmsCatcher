# Gemini 技術架構師 (代號：Mentor) - 專案交接與規劃手冊

**最後更新時間：** 2025-10-14

---

## 專案核心狀態 (Project Core Status)

- **專案目標**：打造一個高效、可擴展的臨時簡訊接收與監控工具。
- **目前架構**：
  - **後端**：Python (Flask) + Selenium + BeautifulSoup。
  - **前端**：原生 HTML/CSS/JS，透過 Flask 的 Jinja2 模板引擎渲染。
  - **設定**：`config.toml` 集中管理所有可調參數。
  - **部署**：支援本地運行及透過 `pyngrok` 產生公開網址。
- **核心功能**：
  - **多網站支援**：已整合 `freereceivesms.com`, `receive-smss.com`, `temp-number.com` 三個網站。
  - **自動廣告攔截**：首次運行時會自動從 GitHub 下載並設定 uBlock Origin 外掛，有效提升爬蟲穩定性與成功率。
  - **來源標示**：前端介面能清晰標示每則簡訊的來源網站。
  - **關鍵字篩選**：支援在後端及前端進行關鍵字篩選。

---

## 💡 關鍵架構洞察 (Key Architectural Insights)

1.  **解耦設計 (Decoupled Design)**：
    - `main.py` 專注於 Web 服務和流程控制。
    - `scraper_core.py` 專注於爬蟲邏輯，並透過 `scrape_all_sites` 函式作為統一入口，根據 URL 分派到對應的爬蟲函式。
    - `config.toml` 專注於設定。這種分離使得新增或修改爬蟲邏輯時，不需要改動主應用程式。

2.  **可複用的爬蟲工具 (Reusable Scraper Tools)**：
    - **自動廣告攔截器**：`create_adblocking_options()` 提供了一個全自動、跨平台的廣告攔截解決方案。它會自動處理 uBlock Origin 外掛的下載與設定，所有爬蟲函式都應使用此工具來初始化 Selenium，以應對充滿廣告的目標網站。

3.  **可擴展的資料結構 (Scalable Data Structure)**：
    - 所有爬蟲函式回傳的資料都包含一個 `source` 鍵。這個小設計是前端能夠清晰展示訊息來源的關鍵，也為未來可能的、更複雜的前端邏輯打下基礎。

---

## 開發歷程與問題解決檔案 (Dev Log & Problem Solving)

本次任務是整合 `temp-number.com` 網站，期間遇到數個典型的爬蟲與自動化挑戰，以下是解決過程的記錄：

1.  **挑戰：網站使用 JavaScript 動態載入內容**
    - **問題**：初期嘗試使用 `web_fetch` 等簡單工具獲取頁面，只能得到靜態的國家列表，無法獲取由 JS 動態產生的電話號碼列表。
    - **解決方案**：確認必須使用 `Selenium` 模擬真實瀏覽器行為，等待 JS 執行完畢後才能抓取到完整 HTML。專案原有架構已支援 Selenium，因此沿用此技術路線。

2.  **挑戰：Windows 環境下的終端編碼錯誤 (`UnicodeEncodeError`)**
    - **問題**：在偵錯過程中，嘗試直接 `print(driver.page_source)` 到 Windows 終端機，但因頁面包含特殊字元 (如 `✔`) 而 `cp950` 編碼不支援，導致 `UnicodeEncodeError`，無法看到輸出。
    - **解決方案**：放棄直接打印到主控台的思路，改為將 `page_source` 以 `UTF-8` 編碼明確寫入一個臨時的 `.html` 檔案。這個方法完全繞過了平台和終端編碼的限制，是更穩健的偵錯手段。

3.  **挑戰：找到正確的 CSS 選取器**
    - **問題**：初步使用的 CSS 選取器 (`a.stretched-link`) 是錯誤的，導致 `WebDriverWait` 超時，爬蟲失敗。
    - **解決方案**：透過上一步生成的 `debug.html` 檔案，仔細分析實際的 HTML 結構，最終確定了正確的選取器 (`a.country-link`) 和號碼文字所在的 `h4` 標籤，成功解決問題。

4.  **挑戰：如何實現可部署、全自動的廣告攔截**
    - **問題**：`temp-number.com` 網站有大量彈出式廣告，嚴重干擾 Selenium 操作。手動安裝外掛的方案無法用於 Colab 等自動化環境。
    - **解決方案**：
        1.  研究發現可透過 `options.add_argument('--load-extension=...')` 載入解壓縮的外掛資料夾。
        2.  為避免手動下載，進一步研究發現可從 uBlock Origin 的官方 GitHub Releases 頁面找到穩定版的 `.zip` 下載連結。
        3.  最終在 `scraper_core.py` 中建立了 `setup_adblocker` 函式，使用 `requests` 和 `zipfile` 函式庫，實現了在程式首次運行時自動檢查、下載、解壓縮外掛的完整自動化流程。

---

## 交接注意事項 (Handover Notes)

-   **自動廣告攔截**：專案現在具備全自動的廣告攔截能力。首次運行時，會自動從 uBlock Origin 的官方 GitHub 下載外掛並解壓縮到 `extensions` 資料夾。此資料夾已被加入 `.gitignore`，不應提交至版本控制。
-   **新增爬蟲**：若要支援新網站，請遵循 `tempnumber_...` 函式的模式：
    1.  在 `scraper_core.py` 中建立新的 `[sitename]_find_active_numbers` 和 `[sitename]_check_single_number` 函式。
    2.  務必使用 `create_adblocking_options()` 來建立 Selenium Options。
    3.  在 `scrape_all_sites` 中新增 `elif` 區塊，呼叫你的新函式，並記得為結果加上 `source` 標籤。
-   **環境設定**：確保 `config.toml` 存在且格式正確。若要在公網訪問，`ngrok_auth_token` 是必須的。
-   **依賴管理**：專案使用 `uv` 管理依賴。在修改套件後，應執行 `uv sync` 來同步環境。
-   **網站變動風險**：爬蟲程式高度依賴目標網站的 HTML 結構。如果目標網站改版，對應的爬蟲函式就需要更新。`scraper_core.py` 是除錯的主要地點。