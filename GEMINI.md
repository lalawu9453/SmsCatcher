# Gemini 技術架構師 (代號：Mentor) - 專案交接與規劃手冊

**最後更新時間：** 2025-10-14

---

## 專案核心狀態 (Project Core Status)

- **專案目標**：打造一個高效、可擴展的臨時簡訊接收與監控工具。
- **目前架構**：
  - **後端**：Python (Flask) + Selenium + BeautifulSoup。
  - **前端**：原生 HTML/CSS/JS，透過 Flask 的 Jinja2 模板引擎渲染。
  - **啟動方式**：支援透過命令列參數 (`--web`, `--ngrok_token`) 進行客製化設定。
  - **設定**：`config.toml` 集中管理所有可調參數。
- **核心功能**：
  - **多網站支援**：已整合 `freereceivesms.com`, `receive-smss.com`, `temp-number.com` 三個網站。
  - **自動廣告攔截**：首次運行時會自動從 GitHub 下載並設定 uBlock Origin 外掛，有效提升爬蟲穩定性與成功率。
  - **來源標示**：前端介面能清晰標示每則簡訊的來源網站，並以不同顏色區分。
  - **關鍵字篩選**：支援在後端及前端進行關鍵字篩選。

---

## 💡 關鍵架構洞察 (Key Architectural Insights)

1.  **命令列介面 (CLI) 整合**：
    - 透過 Python 內建的 `argparse` 函式庫，為應用程式提供了清晰、標準化的命令列介面。
    - 所有啟動參數（如爬取目標、ngrok權杖）都由 `argparse` 統一管理，取代了舊有的、分散的手動 `sys.argv` 解析，大幅提升了程式的穩健性和可維護性。

2.  **可複用的爬蟲工具 (Reusable Scraper Tools)**：
    - **自動廣告攔截器**：`create_adblocking_options()` 提供了一個全自動、跨平台的廣告攔截解決方案。它會自動處理 uBlock Origin 外掛的下載與設定，所有爬蟲函式都應使用此工具來初始化 Selenium，以應對充滿廣告的目標網站。

3.  **資料驅動的前端樣式 (Data-Driven Frontend Styling)**：
    - 透過在 `index.html` 模板中動態生成 CSS class (`source-{{ item.source.lower()... }}`），我們將後端傳遞的資料 (`item.source`) 與前端的視覺表現直接掛鉤。
    - 這種方法讓 CSS 可以針對不同的資料來源定義獨立的樣式（如顏色），使得在未來新增網站來源時，只需增加對應的 CSS 規則即可，無需修改模板邏輯。

---

## 開發歷程與問題解決檔案 (Dev Log & Problem Solving)

1.  **功能：整合 `temp-number.com` 網站**
    - **挑戰**：網站使用 JS 動態載入內容，且充滿廣告，直接爬取困難。
    - **解決方案**：
        1.  使用 `Selenium` 模擬真實瀏覽器行為以執行 JS。
        2.  開發了 `setup_adblocker` 函式，實現首次運行時自動下載並載入 uBlock Origin 外掛，從根本上解決了廣告干擾問題。
        3.  透過將 `page_source` 寫入本地檔案進行偵錯，解決了 Windows 終端 `UnicodeEncodeError` 的問題，並成功找到了正確的 CSS 選取器。

2.  **功能：為來源標籤上色**
    - **挑戰**：如何根據後端傳來的 `source` 字串，顯示不同的顏色。
    - **解決方案**：在 Jinja2 模板中，將 `source` 字串轉換為一個 CSS class 名稱，然後在 `.css` 檔案中為每個 class 定義不同的 `background-color`。

3.  **功能：新增命令列啟動參數**
    - **挑戰**：讓使用者可以靈活選擇要爬取的網站，而不是每次都爬取全部。
    - **解決方案**：
        1.  引入 `argparse` 函式庫。
        2.  重構 `scrape_all_sites` 函式，使其接收一個 `target_urls` 列表作為參數，實現了核心邏輯與資料來源的解耦。
        3.  在 `main.py` 中設定 `--web` 參數，根據使用者輸入來建構 `target_urls` 列表，並將其傳遞給背景更新執行緒。
        4.  **重構**：將原有的 `--ngrok_token` 手動解析邏輯也統一整合到 `argparse` 中，使參數管理更為一致和優雅。

---

## 交接注意事項 (Handover Notes)

-   **啟動方式**：現在可以透過命令列參數啟動程式。使用 `uv run python main.py --help` 來查看所有可用選項。
    -   `--web {1,2,all}`：控制要爬取的網站。
    -   `--ngrok_token YOUR_TOKEN`：在啟動時直接提供 ngrok 權杖。
-   **自動廣告攔截**：專案現在具備全自動的廣告攔截能力。首次運行時，會自動從 uBlock Origin 的官方 GitHub 下載外掛並解壓縮到 `extensions` 資料夾。此資料夾已被加入 `.gitignore`，不應提交至版本控制。
-   **新增爬蟲**：若要支援新網站，請遵循 `tempnumber_...` 函式的模式：
    1.  在 `scraper_core.py` 中建立新的 `[sitename]_find_active_numbers` 和 `[sitename]_check_single_number` 函式。
    2.  務必使用 `create_adblocking_options()` 來建立 Selenium Options。
    3.  在 `scrape_all_sites` 中新增 `elif` 區塊，呼叫你的新函式，並記得為結果加上 `source` 標籤。
-   **環境設定**：確保 `config.toml` 存在且格式正確。若要在公網訪問，`ngrok_auth_token` 是必須的。
-   **依賴管理**：專案使用 `uv` 管理依賴。在修改套件後，應執行 `uv sync` 來同步環境。
-   **網站變動風險**：爬蟲程式高度依賴目標網站的 HTML 結構。如果目標網站改版，對應的爬蟲函式就需要更新。`scraper_core.py` 是除錯的主要地點。
