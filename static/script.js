// 格式化關鍵字清單為逗號分隔的字串
function formatKeywords(keywords) {
    return Array.isArray(keywords) ? keywords.join(', ') : '';
}

// 頁面載入時設定初始值
document.addEventListener('DOMContentLoaded', () => {
    // initialInclude, initialExclude, and initialMode are expected to be global variables
    // defined in the HTML before this script is loaded.
    if (typeof initialInclude !== 'undefined') {
        document.getElementById('must_include').value = formatKeywords(initialInclude);
    }
    if (typeof initialExclude !== 'undefined') {
        document.getElementById('must_exclude').value = formatKeywords(initialExclude);
    }
    if (typeof initialMode !== 'undefined') {
        document.getElementById('filter_mode').value = initialMode;
    }
});

// 提交表單時將逗號分隔字串轉換為 JSON 陣列
function prepareSubmit() {
    const includeInput = document.getElementById('must_include').value;
    const excludeInput = document.getElementById('must_exclude').value;
    
    // 將逗號分隔的字串轉換為陣列
    const includeArray = includeInput.split(',').map(s => s.trim()).filter(s => s.length > 0);
    const excludeArray = excludeInput.split(',').map(s => s.trim()).filter(s => s.length > 0);
    
    // 將陣列存入隱藏欄位 (JSON 格式)
    document.getElementById('json_include').value = JSON.stringify(includeArray);
    document.getElementById('json_exclude').value = JSON.stringify(excludeArray);
    
    return true; // 允許表單提交
}