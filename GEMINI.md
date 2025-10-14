# Gemini 技術架構師 (代號：Mentor) - 專案交接與規劃手冊

**最後更新時間：** 2025-10-14

---

## 專案核心狀態 (Project Core Status)

- **專案目標**：打造一個高效、可擴展、多語言的臨時簡訊接收與監控工具。
- **目前架構**：
  - **後端**：Python (Flask) + Selenium + BeautifulSoup。
  - **前端**：原生 HTML/CSS/JS，透過 Flask 的 Jinja2 模板引擎渲染。
  - **國際化 (i18n)**：透過 `lang.py` 模組集中管理所有使用者介面文字。
  - **啟動方式**：支援透過命令列參數 (`--web`, `--lan`, `--ngrok_token`) 進行客製化設定。
- **核心功能**：
  - **多網站支援**：已整合 `freereceivesms.com`, `receive-smss.com`, `temp-number.com`。
  - **多語言介面**：支援繁體中文 (`zh`) 和英文 (`en`) 的終端及網頁介面。
  - **自動廣告攔截**：首次運行時自動下載並設定 uBlock Origin，提升爬蟲穩定性。
  - **來源標示**：前端清晰標示每則簡訊的來源網站，並以不同顏色區分。

---

## 💡 關鍵架構洞察 (Key Architectural Insights)

1.  **集中式國際化 (Centralized i18n) 架構**：
    - **設計思想**：將所有面向使用者的文字（無論是終端輸出還是網頁內容）從業務邏輯中完全分離，集中到 `lang.py` 檔案中進行管理。
    - **實現方式**：
        1.  `lang.py` 內建立一個包含多語言（`zh`, `en`）字典的 `STRINGS` 變數。
        2.  `main.py` 在啟動時根據 `--lan` 參數，選擇一個語言字典 (`lang_dict`)。
        3.  此 `lang_dict` 被作為參數，沿著 `main.py` -> `update_cache` -> `scrape_all_sites` -> 各爬蟲函式的呼叫鏈，一路傳遞下去。
        4.  同時，`lang_dict` 也被傳遞給 Flask 的 `render_template` 函式，供 `index.html` 使用。
    - **優點**：此架構確保了資料（文字）與視圖（顯示方式）的徹底分離。未來若要新增語言（如日文 `ja`），只需在 `lang.py` 中新增一個字典，完全無需改動任何程式邏輯。

2.  **命令列介面 (CLI) 整合**：
    - 透過 Python 內建的 `argparse` 函式庫，為應用程式提供了清晰、標準化的命令列介面。
    - 所有啟動參數都由 `argparse` 統一管理，並提供自動生成的 `--help` 文件，大幅提升了程式的易用性和可維護性。

3.  **資料驅動的前端樣式 (Data-Driven Frontend Styling)**：
    - 透過在 `index.html` 模板中動態生成 CSS class (`source-{{ item.source.lower()... }}`），我們將後端傳遞的資料與前端的視覺表現直接掛鉤，讓樣式可以根據資料變化，增強了前端的靈活性。

---

## 開發歷程與問題解決檔案 (Dev Log & Problem Solving)

1.  **功能：實現完整國際化 (i18n)**
    - **挑戰**：如何將散落在 `main.py`, `scraper_core.py`, `index.html` 中的所有中文文字，替換為可根據參數動態切換的結構？
    - **解決方案**：
        1.  **建立 `lang.py`**：將所有文字抽象成鍵值對，存入 `lang.py`。
        2.  **重構呼叫鏈**：修改了幾乎所有的核心函式簽名，增加了 `lang_dict` 參數，確保語言字典能從主程式一路傳遞到最深處的爬蟲函式。
        3.  **重構網頁模板**：將 `index.html` 中所有寫死的中文替換為 Jinja2 變數 `{{ lang.KEY }}`。
        4.  **修正測試**：在重構後，主動運行測試，發現了 `pytest` 依賴缺失 (`pytest-mock`) 和測試案例本身邏輯過時（斷言了舊的中文文字）等問題，並逐一修復，確保了重構的正確性。

2.  **功能：新增命令列啟動參數**
    - **挑戰**：讓使用者可以靈活選擇要爬取的網站，而不是每次都爬取全部。
    - **解決方案**：
        1.  引入 `argparse` 函式庫。
        2.  重構 `scrape_all_sites` 函式，使其接收一個 `target_urls` 列表作為參數，實現了核心邏輯與資料來源的解耦。
        3.  **重構**：將原有的 `--ngrok_token` 手動解析邏輯也統一整合到 `argparse` 中，使參數管理更為一致和優雅。

---

## 交接注意事項 (Handover Notes)

-   **啟動方式**：現在可以透過命令列參數啟動程式。使用 `uv run python main.py --help` 來查看所有可用選項。
    -   `--web {1,2,3,all}`：控制要爬取的網站。
    -   `--lan {zh,en}`：設定終端和網頁的顯示語言。
    -   `--ngrok_token YOUR_TOKEN`：在啟動時直接提供 ngrok 權杖。
-   **新增/修改文字**：若要新增或修改任何使用者介面的文字，**請勿**在 `main.py` 或 `index.html` 中寫死。請至 `lang.py` 檔案，找到對應的鍵，並同時修改 `zh` 和 `en` 字典中的值。
-   **新增爬蟲**：若要支援新網站，請遵循 `CONTRIBUTING.md` 中的「新增爬蟲撰寫框架」指南。記得將 `lang_dict` 參數傳遞給您的新函式。
-   **環境設定**：確保 `config.toml` 存在且格式正確。`uv sync` 用於同步依賴。