import requests
import os
import json

# WordPress 配置
WP_URL = "https://www.contentplatform.info/wp-json/wp/v2"
WP_USER = "reporter@megasmarter.com"
WP_PWD = "D4z8 YonO qKzl RTTw 5k6e SswB"

def download_tg_file(file_id, bot_token):
    """透過 Telegram API 下載使用者上傳的照片"""
    file_info = requests.get(f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}").json()
    file_path = file_info['result']['file_path']
    file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    response = requests.get(file_url)
    return response.content, file_path.split('/')[-1]

def upload_to_wp(file_content, filename):
    """將下載的內容上傳到 WordPress"""
    try:
        response = requests.post(
            f"{WP_URL}/media",
            files={'file': (filename, file_content, 'image/jpeg')},
            auth=(WP_USER, WP_PWD),
            timeout=30
        )
        if response.status_code == 201:
            result = response.json()
            return result.get('id'), result.get('source_url'), None
        else:
            return None, None, f"HTTP {response.status_code}"
    except Exception as e:
        return None, None, str(e)

def post_with_tg_photo(title, content, category_id, file_ids, bot_token):
    """主程序：下載 -> 上傳 WP -> 發布文章"""
    media_data = []
    errors = []
    
    # 下載並上傳所有圖片
    for fid in file_ids:
        file_content, filename = download_tg_file(fid, bot_token)
        media_id, media_url, error = upload_to_wp(file_content, filename)
        
        if media_id:
            media_data.append({"id": media_id, "url": media_url})
        else:
            errors.append(f"{fid}: {error}")
    
    if not media_data:
        return {"success": False, "errors": errors}
    
    # 建立內容（第一張為精選圖片）
    final_content = f'<p><img src="{media_data[0]["url"]}" alt=""/></p>'
    for img in media_data[1:]:
        final_content += f'<p><img src="{img["url"]}" alt=""/></p>'
    final_content += content
    
    # 發布文章
    payload = {
        'title': title,
        'content': final_content,
        'categories': [category_id],
        'status': 'draft',
        'featured_media': media_data[0]['id']
    }
    
    response = requests.post(f"{WP_URL}/posts", json=payload, auth=(WP_USER, WP_PWD))
    
    if response.status_code == 201:
        return {
            "success": True,
            "link": response.json().get('link'),
            "media_uploaded": len(media_data),
            "errors": errors
        }
    else:
        return {
            "success": False,
            "errors": errors + [f"POST failed: HTTP {response.status_code}"]
        }
