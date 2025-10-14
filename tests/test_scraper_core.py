
import pytest
from scraper_core import is_within_last_hour, apply_keyword_filter

# ==========================================
# 測試 is_within_last_hour 函式
# ==========================================

@pytest.mark.parametrize("time_text, expected", [
    ("5 分钟前", True),
    ("59 分钟前", True),
    ("1 小时前", False),
    ("2 小时前", False),
    ("10 minutes ago", True),
    ("59 minutes ago", True),
    ("1 hour ago", False),
    ("2 hours ago", False),
    ("30 秒前", True),
    ("seconds ago", True),
    ("未知格式", False),
    ("", False),
])
def test_is_within_last_hour(time_text, expected):
    """測試時間判斷函式是否能正確處理不同格式的時間文字。"""
    assert is_within_last_hour(time_text) == expected

# ==========================================
# 測試 apply_keyword_filter 函式
# ==========================================

@pytest.fixture
def sample_numbers_data():
    """提供一個固定的、用於測試的爬蟲結果範例。"""
    return [
        {
            'number': '+111',
            'url': 'http://example.com/111',
            'last_sms': 'Your code is 1234 for Google.',
            'smss': ['Your code is 1234 for Google.', 'Hello from OpenAI.']
        },
        {
            'number': '+222',
            'url': 'http://example.com/222',
            'last_sms': 'Your verification code for Microsoft is 5678.',
            'smss': ['Your verification code for Microsoft is 5678.']
        },
        {
            'number': '+333',
            'url': 'http://example.com/333',
            'last_sms': 'A new login from Gemini.',
            'smss': ['A new login from Gemini.', 'This is a test message.']
        },
    ]

def test_filter_no_keywords(sample_numbers_data):
    """測試沒有任何關鍵字時，應返回所有原始資料。"""
    result = apply_keyword_filter(sample_numbers_data, [], [])
    assert len(result) == 3

def test_filter_with_include_keywords(sample_numbers_data):
    """測試'包含'關鍵字篩選。"""
    # 測試大小寫不敏感
    result = apply_keyword_filter(sample_numbers_data, ['google', 'Test'], [])
    assert len(result) == 2
    assert result[0]['number'] == '+111' # 包含 Google
    assert result[1]['number'] == '+333' # 包含 test

def test_filter_with_exclude_keywords(sample_numbers_data):
    """測試'排除'關鍵字篩選。"""
    result = apply_keyword_filter(sample_numbers_data, [], ['Microsoft'])
    assert len(result) == 2
    assert result[0]['number'] == '+111'
    assert result[1]['number'] == '+333'

def test_filter_with_both_include_and_exclude(sample_numbers_data):
    """測試同時使用'包含'和'排除'關鍵字。"""
    # 包含 'code'，但排除 'Microsoft'
    result = apply_keyword_filter(sample_numbers_data, ['code'], ['Microsoft'])
    assert len(result) == 1
    assert result[0]['number'] == '+111'

def test_filter_empty_input():
    """測試當輸入為空列表時，應返回空列表。"""
    result = apply_keyword_filter([], ['google'], ['microsoft'])
    assert len(result) == 0

# ==========================================
# 煙霧測試 (Smoke Test) for Scrapers
# ==========================================

from scraper_core import tempnumber_find_active_numbers
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import tomli
from lang import get_lang # 匯入語言模組

def test_tempnumber_scraper_smoke_test():
    """
    對 temp-number.com 的爬蟲執行一個基本的煙霧測試。
    這個測試會實際執行爬蟲，但只驗證它是否能成功完成並返回一個列表，
    而不檢查列表的具體內容。這有助於捕捉重大的執行錯誤。
    """
    print("\n[*] 執行 temp-number.com 爬蟲的煙霧測試...")
    try:
        with open("config.toml", "rb") as f:
            config = tomli.load(f)
        user_agent = config.get('headers', {}).get('User-Agent', 'Mozilla/5.0')
        base_url = "https://temp-number.com/"
        lang_dict = get_lang('en') # 初始化語言字典
        
        print("[*]   - 初始化 ChromeDriver...")
        service = Service(ChromeDriverManager().install())
        
        print("[*]   - 執行 tempnumber_find_active_numbers...")
        # 傳遞 lang_dict 參數
        result = tempnumber_find_active_numbers(service, base_url, user_agent, lang_dict)
        
        # 斷言：結果必須是一個列表 (即使是空列表)
        assert isinstance(result, list)
        print(f"[*]   - 測試成功，函式回傳了一個列表，長度為 {len(result)}。")
        
    except Exception as e:
        pytest.fail(f"temp-number.com 的煙霧測試因異常而失敗: {e}")

