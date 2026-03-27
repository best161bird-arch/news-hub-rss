#!/usr/bin/env python3
"""
RSS 10 軌全能矩陣腳本 (GMT+8 修正版 + 精密排版)
依 J 欄城市分流處理邏輯
"""

import os
import json
import base64
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import email.utils
import re
from urllib.parse import quote, urlparse, parse_qs, urlencode

# ============ 環境變數 ============
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_EMAIL = os.getenv("GITHUB_EMAIL", "bot@example.com")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

# ============ 時區設定 (GMT+8 台灣時間) ============
TAIPEI_TZ = timezone(timedelta(hours=8))

# ============ 分類定義 ============
CATEGORIES = {
    '政治': 'news_politics.xml',
    '產經': 'news_economy.xml',
    '地方': 'news_local.xml',
    '社會': 'news_society.xml',
    '生活': 'news_lifestyle.xml',
    '寵物': 'news_pets.xml',
    '健康': 'news_health.xml',
    '藝文': 'news_culture.xml',
    '專欄': 'news_column.xml'
}

CATEGORY_TITLES = {
    '政治': '報新聞Mega NEWS - 政治頻道',
    '產經': '報新聞Mega NEWS - 產經頻道',
    '地方': '報新聞Mega NEWS - 地方頻道',
    '社會': '報新聞Mega NEWS - 社會頻道',
    '生活': '報新聞Mega NEWS - 生活頻道',
    '寵物': '報新聞Mega NEWS - 寵物頻道',
    '健康': '報新聞Mega NEWS - 健康頻道',
    '藝文': '報新聞Mega NEWS - 藝文頻道',
    '專欄': '報新聞Mega NEWS - 專欄頻道',
    'All': '報新聞Mega NEWS - 全部總匯'
}

# ============ GitHub API ============
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents"

def get_github_file_sha(filepath):
    response = requests.get(
        f"{GITHUB_API_URL}/{filepath}",
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
    )
    if response.status_code == 200:
        return response.json()["sha"]
    return None

def push_to_github(filepath, content, message):
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": message,
        "content": encoded_content,
        "author": {"name": "OpenClaw Bot", "email": GITHUB_EMAIL}
    }
    
    sha = get_github_file_sha(filepath)
    if sha:
        data["sha"] = sha
    
    response = requests.put(
        f"{GITHUB_API_URL}/{filepath}",
        headers={"Authorization": f"token {GITHUB_TOKEN}"},
        json=data
    )
    
    if response.status_code in [200, 201]:
        return True, response.json()["content"]["html_url"]
    else:
        return False, f"Error: {response.status_code}"

# ============ Google Sheets ============
def get_gs_client():
    # 環境變數可能已經是 dict 或 JSON 字串
    if isinstance(GOOGLE_SHEETS_CREDENTIALS, dict):
        creds_json = GOOGLE_SHEETS_CREDENTIALS
    else:
        creds_json = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

def get_approved_articles():
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    all_values = sheet.get_all_values()
    
    if len(all_values) < 2:
        return []
    
    approved = []
    
    for row_idx, row in enumerate(all_values[1:], start=2):
        if len(row) <= 6:
            continue
            
        status = row[6].strip() if len(row) > 6 else ""
        
        if status.lower() == 'approved':
            title = row[2].strip() if len(row) > 2 else ""
            content = row[3].strip() if len(row) > 3 else ""
            category = row[4].strip() if len(row) > 4 else ""
            images = row[5].strip() if len(row) > 5 else ""
            original_link = row[8].strip() if len(row) > 8 else ""
            city = row[9].strip() if len(row) > 9 else ""  # J 欄：城市/機關單位
            timestamp = row[0].strip() if len(row) > 0 else ""
            
            approved.append({
                'row': row_idx,
                'title': title,
                'content': content,
                'category': category,
                'images': images,
                'link': original_link,
                'city': city,  # 城市欄位
                'timestamp': timestamp
            })
    
    return approved

# ============ RSS 生成 (GMT+8 + 精密排版) ============
def get_taipei_time():
    return datetime.now(TAIPEI_TZ)

def parse_date_global(date_str):
    if not date_str or date_str.strip() == "":
        return datetime.now(TAIPEI_TZ)
    
    ts = date_str.strip()
    
    if '上午' in ts or '下午' in ts:
        try:
            is_pm = '下午' in ts
            ts_clean = ts.replace('上午', ' ').replace('下午', ' ')
            match = re.search(r'(\d+)[/-](\d+)[/-](\d+)\s+(\d+):(\d+):?(\d*)', ts_clean)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                second = int(match.group(6)) if match.group(6) else 0
                if is_pm and hour != 12:
                    hour += 12
                return datetime(year, month, day, hour, minute, second, tzinfo=TAIPEI_TZ)
        except:
            pass
    
    try:
        match = re.search(r'(\d+)[/-](\d+)[/-](\d+)[T\s](\d+):(\d+):?(\d*)', ts)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5))
            second = int(match.group(6)) if match.group(6) else 0
            return datetime(year, month, day, hour, minute, second, tzinfo=TAIPEI_TZ)
    except:
        pass
    
    return datetime.now(TAIPEI_TZ)

def to_rfc822_global(date_obj):
    if date_obj.tzinfo is None:
        date_obj = date_obj.replace(tzinfo=TAIPEI_TZ)
    return email.utils.format_datetime(date_obj)

def format_pubdate(timestamp_str):
    dt = parse_date_global(timestamp_str)
    return to_rfc822_global(dt)

def process_image_url(raw_url, city):
    """
    圖片 URL 處理邏輯：
    - 若為『新北市政府』：執行 URL 百分比編碼（Percent-Encoding），且在 CDATA 內使用原始 & 符號
    - 若為其餘城市：維持原始網址格式，禁止執行編碼
    """
    if not raw_url:
        return ""
    
    # 去除分號後的內容（只取第一張圖）
    raw_url = raw_url.split(';')[0].strip()
    
    if not raw_url or raw_url in ["無圖片", "Pending", ""]:
        return ""
    
    # 新北市政府：執行 URL 百分比編碼
    if city == "新北市政府":
        try:
            parsed = urlparse(raw_url)
            query_params = parse_qs(parsed.query, keep_blank_values=True)
            # 對每個參數值進行百分比編碼
            encoded_params = {}
            for key, values in query_params.items():
                encoded_params[key] = [quote(v) for v in values]
            encoded_query = urlencode(encoded_params, doseq=True)
            first_img = parsed._replace(query=encoded_query).geturl()
        except Exception as e:
            # 如果編碼失敗，使用原始 URL
            first_img = raw_url
    else:
        # 其餘城市：維持原始網址格式
        first_img = raw_url
    
    return first_img

def generate_rss_xml(articles, category_name, filename):
    if not articles:
        articles = []
    
    articles = articles[:30]
    
    taipei_time = get_taipei_time()
    rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>{CATEGORY_TITLES.get(category_name, '報新聞Mega NEWS')}</title>
    <link>https://www.contentplatform.info</link>
    <description>最新新聞資訊 - {category_name}頻道</description>
    <language>zh-tw</language>
    <lastBuildDate>{taipei_time.strftime("%a, %d %b %Y %H:%M:%S +0800")}</lastBuildDate>
    <atom:link href="https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}" rel="self" type="application/rss+xml"/>
'''
    
    for article in articles:
        title = article['title']
        content = article['content']
        category = article['category']
        images = article['images']
        timestamp = article.get('timestamp', '')
        link = article.get('link', '')
        city = article.get('city', '').strip() if article.get('city') else ''
        
        # 拆分段落
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        
        # 處理圖片：根據 J 欄城市分流
        first_img = process_image_url(images, city)
        
        # 精密插入圖片 - 僅顯示第一張代表圖
        description = ""
        
        if first_img:
            # CDATA 內使用原始 &（非 &amp;）
            description += f'<img src="{first_img}" />\n'
        
        for i, para in enumerate(paragraphs):
            description += f"<p>{para}</p>\n"
        
        pub_date = format_pubdate(timestamp)
        
        # 生成 GUID - 使用 I 欄原始連結
        # 必須對 link 進行 XML 轉義（將 & 替換為 &amp;）
        link_escaped = link.strip().replace('&', '&amp;') if link and link.strip() else ""
        
        if link_escaped:
            guid = link_escaped
            item_link = link_escaped
        else:
            row_num = str(article.get('row', ''))
            guid = f"{row_num}_{timestamp}" if row_num else timestamp
            item_link = f"https://www.contentplatform.info/{row_num}"
        
        rss += f'''    <item>
        <title><![CDATA[{title}]]></title>
        <link>{item_link}</link>
        <description><![CDATA[{description}]]></description>
        <category>{category}</category>
        <pubDate>{pub_date}</pubDate>
        <guid isPermaLink="false">{guid}</guid>
    </item>
'''
    
    rss += '''</channel>
</rss>'''
    
    return rss

# ============ 主程式 ============
def main():
    print("=" * 60)
    print("10 軌 RSS 全能矩陣同步腳本 (GMT+8 + 精密排版)")
    print("=" * 60)
    
    print("\n[1] 全量掃描 Google Sheets 中狀態為 Approved 的文章...")
    all_articles = get_approved_articles()
    print(f"    找到 {len(all_articles)} 篇 Approved 文章")
    
    if not all_articles:
        print("    ⚠️ 無待發布文章，跳過")
        return
    
    all_articles.sort(key=lambda x: parse_date_global(x.get('timestamp', '')), reverse=True)
    
    print("\n[2] 按分類分組並按時間倒序排列...")
    categorized = defaultdict(list)
    for article in all_articles:
        cat = article.get('category', '').strip()
        if cat in CATEGORIES:
            categorized[cat].append(article)
        else:
            categorized['專欄'].append(article)
    
    for cat in categorized:
        categorized[cat] = sorted(categorized[cat], 
                                   key=lambda x: parse_date_global(x.get('timestamp', '')), 
                                   reverse=True)[:30]
    
    for cat, arts in categorized.items():
        print(f"    - {cat}: {len(arts)} 篇")
    
    print("\n[3] 產生並推送 9 個分類 RSS...")
    results = []
    
    for category, filename in CATEGORIES.items():
        articles = categorized.get(category, [])
        rss_xml = generate_rss_xml(articles, category, filename)
        
        print(f"    📰 {category} ({filename}): {len(articles)} 篇")
        
        message = f"Update {category} RSS - {len(articles)} articles"
        success, result = push_to_github(filename, rss_xml, message)
        
        if success:
            results.append((category, filename, True, result))
            print(f"       ✅ 推送成功")
        else:
            results.append((category, filename, False, result))
            print(f"       ❌ 失敗: {result}")
    
    print("\n[4] 產生並推送總匯 RSS...")
    
    all_articles_sorted = sorted(all_articles, 
                                  key=lambda x: parse_date_global(x.get('timestamp', '')), 
                                  reverse=True)[:30]
    
    all_filename = "news_all.xml"
    all_rss_xml = generate_rss_xml(all_articles_sorted, 'All', all_filename)
    
    print(f"    📊 總匯 (news_all.xml): {len(all_articles_sorted)} 篇")
    
    message = f"Update All News RSS - {len(all_articles_sorted)} articles"
    success, result = push_to_github(all_filename, all_rss_xml, message)
    
    if success:
        results.append(('All', all_filename, True, result))
        print(f"       ✅ 推送成功")
    else:
        results.append(('All', all_filename, False, result))
        print(f"       ❌ 失敗: {result}")
    
    print("\n" + "=" * 60)
    print("RSS GUID 已修正 - 每篇文章都有獨立原始連結")
    print("RSS 圖片處理：")
    print("  - 新北市政府：URL 百分比編碼 + CDATA 內原始 &")
    print("  - 其餘城市：維持原始網址格式")
    print("=" * 60)
    
    print("\n📋 GitHub RAW 網址清單：")
    base_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/"
    
    for category, filename in CATEGORIES.items():
        status = "✅" if any(r[0] == category and r[2] for r in results) else "❌"
        print(f"  {status} {CATEGORY_TITLES[category]}")
        print(f"      {base_url}{filename}")
    
    all_status = "✅" if any(r[0] == 'All' and r[2] for r in results) else "❌"
    print(f"\n  {all_status} {CATEGORY_TITLES['All']}")
    print(f"      {base_url}news_all.xml")

if __name__ == "__main__":
    main()
