
import pytest
from main import app as flask_app # 從 main.py 匯入您的 Flask app

@pytest.fixture
def app():
    """建立並設定一個新的 Flask app 實例用於每個測試。"""
    # 在測試期間，我們不希望真的啟動背景更新執行緒
    # 這裡可以進行一些設定，例如使用測試專用的設定檔
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app

@pytest.fixture
def client(app):
    """一個 Flask 測試客戶端。"""
    return app.test_client()

def test_home_page_loads(client, mocker):
    """測試主頁面 (/) 是否能成功載入並回傳 200 OK。"""
    # 我們需要模擬(mock)背景執行緒中的爬蟲函式，因為在測試時它可能還沒執行完
    # 或者我們不希望在單元測試中觸發真實的爬蟲
    # 這裡我們讓 apply_keyword_filter 回傳一個可預測的空列表
    mocker.patch('main.apply_keyword_filter', return_value=[])
    
    # 模擬 cached_data，讓模板渲染時有資料可用
    mocker.patch('main.cached_data', {
        "raw_numbers": [
            {'number': '+123', 'url': 'http://a.com', 'last_sms': 'sms1', 'smss': ['sms1']}
        ],
        "timestamp": 1234567890
    })

    response = client.get('/')
    assert response.status_code == 200
    # 檢查頁面 h1 標題中的中文字串是否存在，並使用 utf-8 編碼
    assert "活躍簡訊號碼".encode('utf-8') in response.data
    assert b"United States" in response.data
