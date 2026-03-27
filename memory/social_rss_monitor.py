#!/usr/bin/env python3
"""
社群發布 RSS 監控與加工自動化腳本 (v2)
來源: contentplatform.info (分頁二)
執行頻率: 每 15 分鐘

功能：
1. RSS 監聽 + 去重
2. 寫入 Google Sheets
3. MiniMax AI 改寫 (FB/IG/Telegram)
"""

import json
import os
import re
import time
import requests
import urllib.parse
import base64
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

# ========== 設定 ==========
RSS_URL = "https://www.contentplatform.info/feed/?cat=28,317,53,23,46,12654,22,21,24,38,3627"
STATE_FILE = "memory/rss-social-state.json"
SPREADSHEET_ID = "1tcK540sTFEoGaNbXhXF-1Pytk-XQsDSlKEXfvWwZ2Yk"
SHEET_NAME = "02_社群發布"
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")

# 重試設定
MAX_RETRIES = 3
RETRY_DELAY = 5

# ========== Google Auth ==========
def get_access_token():
    """取得 Google API access token"""
    raw = os.environ.get("MATON_API_KEY", "")
    creds = json.loads(raw)
    
    header = {"alg": "RS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": creds["client_email"],
        "sub": creds["client_email"],
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
        "scope": "https://www.googleapis.com/auth/spreadsheets"
    }
    
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    
    private_key = serialization.load_pem_private_key(
        creds["private_key"].encode(),
        password=None,
        backend=default_backend()
    )
    
    signature = private_key.sign(
        f"{h_b64}.{p_b64}".encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    s_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    jwt_token = f"{h_b64}.{p_b64}.{s_b64}"
    
    for retry in range(MAX_RETRIES):
        try:
            auth_req = urllib.request.Request(
                "https://oauth2.googleapis.com/token",
                data=urllib.parse.urlencode({
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": jwt_token
                }).encode(),
                method="POST"
            )
            auth_resp = json.load(urllib.request.urlopen(auth_req, timeout=30))
            return auth_resp["access_token"]
        except Exception as e:
            print(f"  [Auth 重試 {retry+1}/{MAX_RETRIES}] {e}")
            time.sleep(RETRY_DELAY)
    
    return None

# ========== Google Sheets ==========
def read_sheet(access_token, range_name):
    """讀取 Sheet 資料"""
    for retry in range(MAX_RETRIES):
        try:
            encoded_range = urllib.parse.quote(range_name, safe='')
            req = urllib.request.Request(
                f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{encoded_range}',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            resp = json.load(urllib.request.urlopen(req, timeout=30))
            return resp.get('values', [])
        except Exception as e:
            print(f"  [讀取重試 {retry+1}/{MAX_RETRIES}] {e}")
            time.sleep(RETRY_DELAY)
    return []

def append_row(access_token, row_data):
    """新增資料列"""
    for retry in range(MAX_RETRIES):
        try:
            # 先取得現有列數
            encoded_range = urllib.parse.quote(f"{SHEET_NAME}!A:A", safe='')
            req = urllib.request.Request(
                f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{encoded_range}:append?valueInputOption=USER_ENTERED',
                data=json.dumps({"values": [row_data]}).encode(),
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
            )
            req.get_method = lambda: 'POST'
            resp = json.load(urllib.request.urlopen(req, timeout=60))
            return True
        except Exception as e:
            print(f"  [寫入重試 {retry+1}/{MAX_RETRIES}] {e}")
            time.sleep(RETRY_DELAY)
    return False

def update_cell(access_token, row, col, value):
    """更新單一儲存格"""
    cell = f"{SHEET_NAME}!{col}{row}"
    encoded_range = urllib.parse.quote(cell, safe='')
    
    for retry in range(MAX_RETRIES):
        try:
            url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{encoded_range}?valueInputOption=USER_ENTERED'
            req = urllib.request.Request(
                url,
                data=json.dumps({"values": [[value]]}).encode(),
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }
            )
            req.get_method = lambda: 'PUT'
            resp = urllib.request.urlopen(req, timeout=30)
            return True
        except Exception as e:
            print(f"  [更新重試 {retry+1}/{MAX_RETRIES}] {e}")
            time.sleep(RETRY_DELAY)
    return False

# ========== RSS 抓取 ==========
def fetch_rss():
    """抓取 RSS feed"""
    for retry in range(MAX_RETRIES):
        try:
            resp = requests.get(RSS_URL, timeout=60)
            resp.encoding = 'utf-8'
            return resp.text
        except Exception as e:
            print(f"  [RSS 重試 {retry+1}/{MAX_RETRIES}] {e}")
            time.sleep(RETRY_DELAY)
    return None

def parse_rss(xml_text):
    """解析 RSS"""
    articles = []
    try:
        item_pattern = r'<item>(.*?)</item>'
        items = re.findall(item_pattern, xml_text, re.DOTALL)
        
        for item in items:
            title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item)
            if not title_match:
                title_match = re.search(r'<title>(.*?)</title>', item)
            title = title_match.group(1).strip() if title_match else ""
            
            link_match = re.search(r'<link>(.*?)</link>', item)
            link = link_match.group(1).strip() if link_match else ""
            
            pubdate_match = re.search(r'<pubDate>(.*?)</pubDate>', item)
            pubdate = pubdate_match.group(1).strip() if pubdate_match else ""
            
            cat_match = re.search(r'<category><!\[CDATA\[(.*?)\]\]></category>', item)
            if not cat_match:
                cat_match = re.search(r'<category>(.*?)</category>', item)
            category = cat_match.group(1).strip() if cat_match else ""
            
            content_match = re.search(r'<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>', item, re.DOTALL)
            content = content_match.group(1).strip() if content_match else ""
            
            img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
            image_url = img_match.group(1) if img_match else ""
            
            if title and link:
                articles.append({
                    "title": title,
                    "link": link,
                    "pubdate": pubdate,
                    "category": category,
                    "content": content,
                    "image": image_url
                })
    except Exception as e:
        print(f"RSS 解析錯誤: {e}")
    
    return articles

# ========== MiniMax AI ==========
def rewrite_with_minimax(title, content, platform):
    """使用 MiniMax API 改寫"""
    if not MINIMAX_API_KEY:
        return None
    
    if platform == "fb":
        prompt = f"""為以下文章撰寫 Facebook 貼文：
標題：{title}
內容：{content[:300]}
要求：導流風格、3個重點、Emoji、Hashtags、附原文連結"""
    elif platform == "ig":
        prompt = f"""為以下文章撰寫 Instagram/Threads 貼文：
標題：{title}
內容：{content[:300]}
要求：視覺感性風格、分段清晰、10個熱門標籤"""
    else:  # telegram
        prompt = f"""為以下文章撰寫 Telegram 貼文：
標題：{title}
內容：{content[:300]}
要求：簡報風格、標題加粗、三行摘要、附連結"""
    
    for retry in range(MAX_RETRIES):
        try:
            import requests as req
            resp = req.post(
                "https://api.minimax.chat/v1/text/chatcompletion_v2",
                headers={
                    "Authorization": f"Bearer {MINIMAX_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "abab6.5-chat",
                    "messages": [
                        {"role": "system", "content": "你是專業社群小編，擅長撰寫吸引人的社群文案。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7
                },
                timeout=60
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        except Exception as e:
            print(f"  [MiniMax 重試 {retry+1}/{MAX_RETRIES}] {e}")
            time.sleep(RETRY_DELAY)
    
    return None

# ========== 主流程 ==========
def main():
    print(f"[{datetime.now()}] === 開始執行社群 RSS 監控 ===")
    
    # 1. 取得 Google 授權
    print("[1/5] 取得 Google 授權...")
    access_token = get_access_token()
    if not access_token:
        print("❌ 無法取得 access token")
        return
    print("✅ 授權成功")
    
    # 2. 讀取現有標題 (去重)
    print("[2/5] 讀取現有標題...")
    existing_data = read_sheet(access_token, f"{SHEET_NAME}!C:C")
    existing_titles = set()
    for row in existing_data[1:]:  # 跳過標題列
        if row:
            existing_titles.add(row[0].strip())
    print(f"   現有文章: {len(existing_titles)} 篇")
    
    # 3. 抓取 RSS
    print("[3/5] 抓取 RSS...")
    xml_text = fetch_rss()
    if not xml_text:
        print("❌ RSS 抓取失敗")
        return
    
    articles = parse_rss(xml_text)
    print(f"   RSS 文章總數: {len(articles)} 篇")
    
    # 4. 過濾新文章
    new_articles = [a for a in articles if a['title'] not in existing_titles]
    print(f"   新文章: {len(new_articles)} 篇")
    
    if new_articles:
        # 5. 寫入新文章 (分批處理)
        print("[4/5] 寫入新文章...")
        
        # 取得現有列數
        all_data = read_sheet(access_token, f"{SHEET_NAME}!A:A")
        start_row = len(all_data) + 1
        
        for idx, article in enumerate(new_articles):
            print(f"   處理 {idx+1}/{len(new_articles)}: {article['title'][:30]}...")
            
            # 產生編號
            today = datetime.now().strftime("%Y%m%d")
            serial = f"{today}-{str(start_row + idx).zfill(4)}"
            
            # 清理 HTML 標籤
            clean_content = re.sub(r'<[^>]+>', '', article['content'])[:2000]
            
            row = [
                article['pubdate'],  # A
                f"SOC-{serial}",     # B
                article['title'],    # C
                clean_content,       # D
                article['category'], # E
                article['image'],    # F
                article['link'],     # G
                "", "", "", "", "",  # H-M (預留)
                "Social_Pending"     # N
            ]
            
            if append_row(access_token, row):
                print(f"      ✅ 已寫入")
                
                # 6. MiniMax AI 改寫 (非同步處理)
                print("[5/5] AI 改寫...")
                
                # FB 文案
                fb_text = rewrite_with_minimax(article['title'], article['content'], "fb")
                if fb_text:
                    update_cell(access_token, start_row + idx, "H", fb_text)
                    print(f"      FB ✅")
                
                # IG 文案
                ig_text = rewrite_with_minimax(article['title'], article['content'], "ig")
                if ig_text:
                    update_cell(access_token, start_row + idx, "J", ig_text)
                    print(f"      IG ✅")
                
                # Telegram 文案
                tg_text = rewrite_with_minimax(article['title'], article['content'], "telegram")
                if tg_text:
                    update_cell(access_token, start_row + idx, "M", tg_text)
                    print(f"      TG ✅")
                
                # 更新狀態
                update_cell(access_token, start_row + idx, "N", "Social_Ready")
            else:
                print(f"      ❌ 寫入失敗")
    
    # 更新狀態檔
    state = {
        "last_check": datetime.now().isoformat() + "Z",
        "spreadsheet_id": SPREADSHEET_ID,
        "sheet_name": SHEET_NAME,
        "new_articles_count": len(new_articles)
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f"\n[{datetime.now()}] === 完成! 新文章: {len(new_articles)} 篇 ===")

if __name__ == "__main__":
    main()
