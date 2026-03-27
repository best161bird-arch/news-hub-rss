import gspread
import os
import json
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# WordPress config (停用，改用 litterbox)
WP_URL = "https://www.contentplatform.info/wp-json/"
WP_USER = "reporter@megasmarter.com"
WP_PWD = "D4z8 YonO qKzl RTTw 5k6e SswB"

def get_gs_client():
    """取得 Google Sheets 客戶端"""
    creds_json = json.loads(os.getenv("GOOGLE_SHEETS_CREDENTIALS"))
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

def upload_to_litterbox(file_path):
    """
    上傳圖片到 litterbox.catbox.moe (臨時圖床)
    回傳: (public_url, error)
    """
    if not file_path or not os.path.exists(file_path):
        return None, "檔案不存在"
    
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://litterbox.catbox.moe/resources/internals/api.php',
                data={'reqtype': 'fileupload', 'time': '1h'},
                files={'fileToUpload': f},
                timeout=60
            )
        
        if response.status_code == 200:
            url = response.text.strip()
            return url, None
        else:
            return None, f"HTTP {response.status_code}: {response.text}"
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.RequestException as e:
        return None, str(e)
    except Exception as e:
        return None, f"Error: {str(e)}"

def write_to_hub(title, content, category, img_url):
    """
    寫入資料到 Google Sheets 中轉站（自動偵測末端模式）
    - 使用 append_row 自動跳過已存在的內容
    - 雙重確認回報最後一行編號
    """
    client = get_gs_client()
    sheet = client.open_by_key(os.getenv("GOOGLE_SHEETS_ID")).sheet1
    
    # 1. 準備資料列
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_to_add = [now, title, content, category, img_url, "Pending"]
    
    # 2. 強制執行 append_row 並指定 insert_data_option
    # 這會確保它跳過所有已存在的內容，直接在最後一行新增
    try:
        sheet.append_row(row_to_add, value_input_option='USER_ENTERED', insert_data_option='INSERT_ROWS')
        
        # 3. 雙重確認：獲取目前最後一行的編號回報
        last_row = len(sheet.get_all_values())
        return f"✅ 已成功寫入第 {last_row} 列。標題：{title}"
    except Exception as e:
        return f"❌ 寫入失敗，錯誤原因：{str(e)}"

def get_pending_articles():
    """取得所有 Pending 狀態的文章"""
    client = get_gs_client()
    sheet = client.open_by_key(os.getenv("GOOGLE_SHEETS_ID")).sheet1
    records = sheet.get_all_records()
    return [r for r in records if r.get('執行狀態', '').strip() == 'Pending']

def update_status(row, status):
    """更新執行狀態"""
    client = get_gs_client()
    sheet = client.open_by_key(os.getenv("GOOGLE_SHEETS_ID")).sheet1
    sheet.update_cell(row, 6, status)
    return f"已更新狀態為：{status}"
