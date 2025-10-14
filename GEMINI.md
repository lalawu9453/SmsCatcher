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
- **核心流程**：
  1. `main.py` 啟動 Flask 服務和一個背景執行緒。
  2. 背景執行緒定時呼叫 `scraper_core.py` 中的 `scrape_all_sites` 函式。
  3. `scrape_all_sites` 根據 `config.toml` 中的 `base_urls` 列表，為每個網站選擇對應的爬蟲函式 (例如 `freereceivesms_find_active_numbers`)。
  4. 爬蟲函式使用 Selenium 獲取號碼列表，並透過 `ThreadPoolExecutor` 併發檢查每個號碼的最新簡訊。
  5. "活躍" 的號碼 (一小時內有新簡訊) 及其簡訊內容被收集起來，存入全域變數 `cached_data`。
  6. 使用者訪問網頁時，Flask 從 `cached_data` 讀取資料，並可根據使用者提交的關鍵字進行即時篩選，最後渲染 `index.html` 模板回傳給使用者。

---

## 💡 關鍵架構洞察 (Key Architectural Insights)

1.  **解耦設計 (Decoupled Design)**：
    - `main.py` 專注於 Web 服務和流程控制。
    - `scraper_core.py` 專注於爬蟲邏輯。
    - `config.toml` 專注於設定。
    - 這種分離使得新增或修改爬蟲邏輯時，不需要改動主應用程式 `main.py`。

2.  **可擴展的爬蟲機制 (Scalable Scraper Mechanism)**：
    - `scrape_all_sites` 函式是擴展新網站的**核心入口**。它透過判斷 URL 中是否包含特定字串 (如 `freereceivesms.com`) 來呼叫對應的爬蟲函式。
    - 只要我們為新網站編寫一個遵循同樣模式 (輸入 `CHROME_SERVICE`, `base_url` 等，輸出活躍號碼列表) 的新函式，並在 `scrape_all_sites` 中加入一個 `elif` 判斷，就能輕易整合。

3.  **效能考量 (Performance Considerations)**：
    - 使用 `ThreadPoolExecutor` 併發檢查號碼，大幅縮短了等待時間。
    - `CHROME_SERVICE` 實例在 `main.py` 中被初始化一次並全域傳遞，避免了每次爬蟲都重新下載和啟動 ChromeDriver 的開銷。
    - 資料快取 (`cached_data`) 機制避免了每次使用者請求都觸發一次完整的爬蟲，提升了前端反應速度。

---

## 進行中的任務：整合新簡訊網站 (In-Progress Task: Integrate New SMS Site)

### 新功能規格 (Feature Specification)

1.  **目標網站**：整合 `https://temp-number.com/` 作為新的簡訊來源。
2.  **核心實現**：
    *   在 `scraper_core.py` 中，建立一個專為 `temp-number.com` 設計的新爬蟲函式 (`tempnumber_find_active_numbers`)。
    *   此函式將負責解析該網站的 HTML 結構，抓取活躍的電話號碼及其最新的簡訊。
3.  **資料結構擴充**：為了在前端區分來源，我們將修改**所有**爬蟲函式回傳的資料結構。每個號碼的字典中，都會新增一個 `source` 鍵，其值為網站的名稱（例如 `'source': 'FreeReceiveSMS'` 或 `'source': 'Temp-Number'`）。
4.  **前端呈現**：
    *   修改 `templates/index.html` 模板。
    *   在顯示每個電話號碼的區塊，利用新增的 `source` 鍵，顯示一個清晰的來源標籤。

### 規劃流程 Todolist (Workflow To-Do List)

-   [x] **步驟一：分析新網站 (`temp-number.com`)**
    -   [x] 使用工具分析目標網站的 HTML，確定電話號碼列表頁和簡訊詳情頁的結構。
-   [x] **步驟二：擴充爬蟲核心 (`scraper_core.py`)**
    -   [x] 建立 `tempnumber_find_active_numbers` 函式。
    -   [x] 在既有的 `freereceivesms_find_active_numbers` 和 `receivesmss_find_active_numbers` 函式回傳的結果中，補上 `source` 鍵。
    -   [x] 在新函式中，實現抓取邏輯，並確保回傳結果包含 `source` 鍵。
-   [x] **步驟三：整合爬蟲調度 (`scraper_core.py`)**
    -   [x] 修改 `scrape_all_sites` 函式，加入 `elif "temp-number.com" in url:` 判斷，以呼叫新建的爬蟲函式。
-   [x] **步驟四：更新前端模板 (`templates/index.html`)**
    -   [x] 在號碼列表的迴圈中，新增一個 `<span>` 或類似標籤來顯示 `{{ item.source }}`。
    -   [x] (可選) 在 `static/style.css` 中為這個新標籤添加簡單樣式，使其更醒目。
-   [x] **步驟五：更新設定檔 (`config.toml`)**
    -   [x] 將 `https://temp-number.com/` 新增到 `base_urls` 列表中。
-   [x] **步驟六：文件與提交**
    -   [x] 將本規劃更新至 `GEMINI.md`。
    -   [x] 在所有開發完成後，執行一次完整的測試，並將相關變更進行版本控制提交。

---

## 交接注意事項 (Handover Notes)

-   **自動廣告攔截**：專案現在具備全自動的廣告攔截能力。首次運行時，`scraper_core.py` 中的 `setup_adblocker` 函式會自動從 uBlock Origin 的官方 GitHub 下載外掛並解壓縮到 `extensions` 資料夾。此後運行將直接使用該外掛，無需手動設定，極大提升了爬蟲的穩定性和部署的便利性。
-   **環境設定**：確保 `config.toml` 存在且格式正確。若要在公網訪問，`ngrok_auth_token` 是必須的。
-   **依賴管理**：專案使用 `uv` 管理依賴。在修改套件後，應執行 `uv sync` 來同步環境。
-   **網站變動風險**：爬蟲程式高度依賴目標網站的 HTML 結構。如果目標網站改版，對應的爬蟲函式就需要更新。`scraper_core.py` 是除錯的主要地點。
-   **IP 封鎖風險**：頻繁爬取可能導致 IP 被目標網站封鎖。目前的併發數 (`max_workers`) 和更新頻率 (`cache_duration_seconds`) 是比較保守的設定，可根據情況調整。
