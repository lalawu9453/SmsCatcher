
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
