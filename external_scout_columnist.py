#!/usr/bin/env python3
"""
專欄偵察兵 - Facebook Columnist Scraper
使用 Apify Task 抓取專欄作家 FB 貼文
"""

import os
import json
import re
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from apify_client import ApifyClient

# ============ 環境變數 ============
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_TASK_ID = "eQkhL4ByyxgvKVeSv"
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat")

# ============ 專欄作家映射 ============
AUTHOR_MAPPING = {
    "eddie.yuan.3": {"name": "袁青", "prefix": "【袁青專欄】", "tag": "袁青時尚學"},
    "stylewalkyc": {"name": "袁青", "prefix": "【袁青專欄】", "tag": "袁青時尚學"},
    "wupoetart": {"name": "吳德亮", "prefix": "【吳德亮專欄】", "tag": "吳德亮"}
}

MONITOR_LIST = [
    "https://www.facebook.com/eddie.yuan.3",
    "https://www.facebook.com/stylewalkyc",
    "https://www.facebook.com/wupoetart"
]

# ============ Google Sheets ============
def get_gs_client():
    creds_json = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

def get_next_column_id(sheet, date_prefix=None):
    all_values = sheet.get_all_values()
    max_num = 0
    prefix = f"COL-{date_prefix}-" if date_prefix else "COL-"
    for row in all_values[1:]:
        if len(row) > 1 and row[1].startswith(prefix):
            try:
                num = int(row[1].split('-')[-1])
                max_num = max(max_num, num)
            except:
                pass
    return f"{prefix}{max_num + 1:04d}"

def write_column_article(article):
    client = get_gs_client()
    # Use new worksheet
    spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
    try:
        sheet = spreadsheet.worksheet("01_專欄文章審核FB")
    except:
        sheet = spreadsheet.add_worksheet(title="01_專欄文章審核FB", rows=1000, cols=10)
        sheet.update('A1:J1', [["時間戳記", "編號", "新聞標題", "新聞內文", "新聞分類", "圖片上傳", "執行狀態", "WP Link", "Original Link", "備註"]])
    
    # Generate COL-YYYYMMDD-XXXX format
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    col_id = get_next_column_id(sheet, today)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    row_data = [
        timestamp, col_id, article['title'], article['content'],
        "專欄", article.get('images', ''), "Pending", "",
        article['original_link'], article.get('author_tag', '')
    ]
    
    sheet.append_row(row_data)
    print(f"    ✅ 已寫入: {col_id} - {article['title'][:30]}...")
    return col_id

# ============ MiniMax AI ============
def rewrite_with_minimax(content, author_name):
    if not MINIMAX_API_KEY:
        return content
    
    prompt = f"""請將以下{author_name}的Facebook貼文改寫為正式的新聞專欄格式：

要求：
1. 保留作者原意與精華
2. 補足背景描述
3. 刪除FB術語
4. 改寫為300-500字專業專欄

原文：{content[:2000]}"""

    try:
        response = requests.post(
            f"{MINIMAX_BASE_URL}/v1/text/chatcompletion_v2?GroupId={MINIMAX_GROUP_ID}",
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}".strip(),
                "Content-Type": "application/json"
            },
            json={
                "model": "minimax-m2.7",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "stream": False
            },
            timeout=300
        )
        # 只取第一行，忽略後續的 data: [DONE] 或額外字元
        first_line = response.text.split('\n')[0]
        result = json.loads(first_line)
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"    ⚠️ MiniMax失敗: {str(e)[:50]}")
        # 如果解析失敗，嘗試 fallback 到 Gemini
        print(f"    🔄 Fallback to Gemini...")
        return rewrite_with_gemini(content, author_name)
    
    return content

# ============ Apify Task 抓取 ============
def scrape_facebook_posts():
    if not APIFY_API_TOKEN:
        print("    ⚠️ 無APIFY_API_TOKEN")
        return []
    
    client = ApifyClient(APIFY_API_TOKEN)
    articles = []
    
    for fb_url in MONITOR_LIST:
        fb_id = fb_url.split('/')[-1]
        author_info = AUTHOR_MAPPING.get(fb_id, {"name": fb_id, "prefix": f"【{fb_id}】", "tag": fb_id})
        
        print(f"    抓取: {fb_url} ({author_info['name']})...")
        
        try:
            task = client.task(APIFY_TASK_ID)
            run = task.call(
                task_input={
                    "startUrls": [{"url": fb_url}],
                    "maxPosts": 2
                },
                wait_secs=180
            )
            
            if run and run.get('defaultDatasetId'):
                dataset = client.dataset(run['defaultDatasetId'])
                posts = list(dataset.iterate_items())
                
                for post in posts[:2]:
                    images = post.get('images', []) or post.get('media', []) or post.get('attachments', [])[:5]
                    post_text = post.get('text', '')[:100]
                    clean_text = re.sub(r'#\w+', '', post_text).strip()
                    # Title format: [專欄作家]｜[FB貼文第一行文字]
                    first_line = post.get('text', '').split('\n')[0][:50]
                    title = f"[{author_info['name']}]｜{first_line}"
                    
                    rewritten = rewrite_with_minimax(post.get('text', ''), author_info['name'])
                    
                    articles.append({
                        'title': title,
                        'content': rewritten,
                        'images': "; ".join([
        img.get('media_url', img.get('url', '')) 
        if isinstance(img, dict) 
        else (img if isinstance(img, str) and ('.jpg' in img or '.png' in img) else '')
        for img in (images or [])
        if img
    ]),
                        'original_link': post.get('url', fb_url),
                        'author_tag': author_info['tag']
                    })
                    print(f"      ✅ 完成")
                    
        except Exception as e:
            print(f"    ⚠️ 失敗: {str(e)[:50]}")
    
    return articles

# ============ 主程式 ============
def main():
    print("=" * 60)
    print("專欄偵察兵 - Apify Task 模式")
    print("=" * 60)
    
    print("\n[1] 抓取 Facebook 專欄...")
    articles = scrape_facebook_posts()
    
    print(f"    共抓取 {len(articles)} 篇")
    
    if articles:
        print("\n[2] 寫入 Sheets (批量寫入)...")
        
        # Get the worksheet
        client = get_gs_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
        try:
            sheet = spreadsheet.worksheet("01_專欄文章審核FB")
        except:
            sheet = spreadsheet.add_worksheet(title="01_專欄文章審核FB", rows=1000, cols=10)
        
        # Build data list first
        data_list = []
        for idx, a in enumerate(articles, 1):
            try:
                col_id = get_next_column_id(sheet)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                row_data = [
                    timestamp, col_id, a['title'], a['content'],
                    "專欄", a.get('images', ''), "Pending", "",
                    a['original_link'], a.get('author_tag', '')
                ]
                data_list.append(row_data)
                print(f"    ✅ 已整理: {col_id} ({idx}/6)")
                
            except Exception as e:
                print(f"    ❌ 整理失敗: {str(e)[:30]}")
        
        # Batch write all at once
        if data_list:
            sheet.append_rows(data_list)
            print(f"    ✅ 批量寫入完成: {len(data_list)} 篇")
    else:
        print("    ⚠️ 無新文章")
    
    print("\n" + "=" * 60)
    print("✅ Task ID 綁定成功，專欄偵察兵已啟動")
    print("=" * 60)

if __name__ == "__main__":
    main()
