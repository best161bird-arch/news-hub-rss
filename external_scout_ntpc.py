#!/usr/bin/env python3
"""
四合一情報偵查兵 - 新北市政府模組 (修正版)
external_scout_ntpc.py

抓取來源：https://www.ntpc.gov.tw/ch/home.jsp?id=e8ca970cde5c00e1
"""

import os
import re
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

# ============ 環境變數 ============
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

# ============ 時區 ============
TAIPEI_TZ = timezone(timedelta(hours=8))

# ============ Headers ============
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

BASE_URL = "https://www.ntpc.gov.tw"

# ============ Google Sheets ============
def get_gs_client():
    if isinstance(GOOGLE_SHEETS_CREDENTIALS, dict):
        creds_json = GOOGLE_SHEETS_CREDENTIALS
    else:
        creds_json = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

def get_existing_links():
    """取得現有 I 欄 Original Link"""
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    all_values = sheet.get_all_values()
    links = set()
    for row in all_values[1:]:
        if len(row) >= 9 and row[8].strip():
            links.add(row[8].strip())
    return links

def generate_id():
    """產生 GOV-NTPC-YYYYMMDD-XXXX 編號"""
    today = datetime.now(TAIPEI_TZ).strftime("%Y%m%d")
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    all_values = sheet.get_all_values()
    max_num = 0
    prefix = f"GOV-NTPC-{today}-"
    for row in all_values[1:]:
        if len(row) >= 2 and row[1].startswith(prefix):
            try:
                num = int(row[1].split('-')[-1])
                max_num = max(max_num, num)
            except:
                pass
    return f"{prefix}{max_num + 1:04d}"

def extract_images_from_detail(html_content):
    """從內頁提取圖片 .album_list .pic img"""
    images = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 從 .album_list .pic img 提取
    album_pics = soup.select('.album_list .pic img')
    if not album_pics:
        album_pics = soup.select('.album img')
    
    for img in album_pics:
        src = img.get('src', '') or img.get('data-src', '')
        if src:
            # 補上前綴
            if src.startswith('/'):
                src = BASE_URL + src
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                images.append(src)
    
    return images[:8]

def insert_images_into_content(content, images):
    """
    圖片插入規則：
    - 首圖：置於內文最上方
    - 二圖：置於第三段落之後
    - 三圖：置於第四段落之後
    - 其餘：依序排於後續段落之後
    - 嚴禁在內文最末端再次附加圖片
    """
    if not images:
        return content
    
    paragraphs = [p for p in content.split('\n') if p.strip()]  # 移除空行
    result = []
    img_idx = 0
    
    for i, para in enumerate(paragraphs):
        result.append(para)
        
        # 首圖：第0個位置
        if i == 0 and img_idx < len(images):
            result.append(f"\n[IMAGE_URL]{images[img_idx]}[/IMAGE_URL]\n")
            img_idx += 1
        # 二圖：第3個位置（第四段後）
        elif i == 3 and img_idx < len(images):
            result.append(f"\n[IMAGE_URL]{images[img_idx]}[/IMAGE_URL]\n")
            img_idx += 1
        # 三圖：第4個位置（第五段後）
        elif i == 4 and img_idx < len(images):
            result.append(f"\n[IMAGE_URL]{images[img_idx]}[/IMAGE_URL]\n")
            img_idx += 1
        # 其餘：每兩段後一張
        elif i > 4 and (i - 5) % 2 == 0 and img_idx < len(images):
            result.append(f"\n[IMAGE_URL]{images[img_idx]}[/IMAGE_URL]\n")
            img_idx += 1
    
    final_content = '\n'.join(result)
    
    # 移除文末重複的 [IMAGE_URL] 標籤
    # 找到最後一個 [IMAGE_URL] 的位置，確保後面沒有其他圖片標籤
    import re
    # 移除結尾處的所有 [IMAGE_URL]xxx[/IMAGE_URL]
    final_content = re.sub(r'\n*\[IMAGE_URL\].*?\[/IMAGE_URL\]\s*$', '', final_content, flags=re.DOTALL)
    
    return final_content.strip()

def scrape_ntpc_news():
    """抓取新北市政府新聞"""
    print("    🌐 抓取新北市政府新聞...")
    
    existing_links = get_existing_links()
    new_articles = []
    
    try:
        # 抓取列表頁
        response = requests.get(
            f"{BASE_URL}/ch/home.jsp?id=e8ca970cde5c00e1",
            headers=HEADERS,
            timeout=30,
            verify=False
        )
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 定位 .list .article 區塊
        list_block = soup.select_one('.list') or soup.select_one('.article_list') or soup.select_one('.news_list')
        
        # 找出包含 dataserno 的連結
        news_links = []
        if list_block:
            articles = list_block.find_all('a', href=True)
            for a in articles:
                href = a.get('href', '')
                # 只取包含 dataserno 的連結
                if 'dataserno' in href:
                    if href.startswith('http'):
                        full_url = href
                    elif href.startswith('/'):
                        full_url = BASE_URL + href
                    else:
                        full_url = BASE_URL + "/" + href
                    
                    title = a.get_text(strip=True)
                    if title and len(title) > 5 and full_url not in existing_links:
                        news_links.append({'url': full_url, 'title': title})
        
        # 如果上面的方法不行，直接從整頁找
        if not news_links:
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'dataserno' in href:
                    if href.startswith('http'):
                        full_url = href
                    elif href.startswith('/'):
                        full_url = BASE_URL + href
                    else:
                        full_url = BASE_URL + "/" + href
                    
                    title = a.get_text(strip=True)
                    if title and len(title) > 5 and full_url not in existing_links:
                        news_links.append({'url': full_url, 'title': title})
        
        # 去重
        seen = set()
        unique_links = []
        for link in news_links:
            if link['url'] not in seen:
                seen.add(link['url'])
                unique_links.append(link)
        news_links = unique_links
        
        print(f"    📰 發現 {len(news_links)} 篇新聞")
        
        # 只處理前3篇
        for idx, link_info in enumerate(news_links[:3]):
            url = link_info['url']
            
            # 修正 Original Link：確保包含 /ch/ 路徑
            if '/ch/' not in url:
                # 從 URL 中提取參數，重新構造
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                params = urllib.parse.parse_qs(parsed.query)
                id_val = params.get('id', [''])[0]
                dataserno = params.get('dataserno', [''])[0]
                if id_val and dataserno:
                    url = f"{BASE_URL}/ch/home.jsp?id={id_val}&dataserno={dataserno}"
            
            try:
                # 抓取內頁
                detail_resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
                detail_resp.encoding = 'utf-8'
                detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                
                # 提取標題：從 .d_title 抓取，前面加【新北】，嚴禁包含日期
                title_elem = detail_soup.select_one('.d_title') or \
                            detail_soup.select_one('.title') or \
                            detail_soup.select_one('h1') or \
                            detail_soup.select_one('.subject')
                title = link_info['title']
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # 去除標題中的日期 (如 2026-03-26)
                title = re.sub(r'\d{4}-\d{2}-\d{2}', '', title).strip()
                title = re.sub(r'\d{1,2}\.\d{1,2}\.\d{1,2}', '', title).strip()
                title = f"【新北】{title}"
                
                # 提取內文：從 .edit 內抓取原始文字
                content = ""
                edit_div = detail_soup.select_one('.edit') or \
                           detail_soup.select_one('.article_edit') or \
                           detail_soup.select_one('.d_cont')
                if edit_div:
                    for tag in edit_div.find_all(['script', 'style', 'iframe']):
                        tag.decompose()
                    content = edit_div.get_text(strip=True)
                
                # 如果沒有 .edit，嘗試其他區塊
                if not content:
                    content_div = detail_soup.select_one('.content') or \
                                  detail_soup.select_one('.article_content') or \
                                  detail_soup.select_one('#content') or \
                                  detail_soup.select_one('.main')
                    if content_div:
                        for tag in content_div.find_all(['script', 'style']):
                            tag.decompose()
                        content = content_div.get_text(strip=True)
                
                # 清理內容
                content = re.sub(r'\n+', '\n', content)
                content = re.sub(r' {2,}', ' ', content)
                content = content[:3000]
                
                # 提取圖片
                images = extract_images_from_detail(detail_resp.text)
                
                # 圖文重組
                content_with_images = insert_images_into_content(content, images)
                
                new_articles.append({
                    'title': title,
                    'content': content_with_images,
                    'images': "; ".join(images),
                    'original_link': url
                })
                print(f"      ✅ 完成 ({idx+1}/3): {title[:30]}...")
                
            except Exception as e:
                print(f"      ⚠️ 失敗: {str(e)[:30]}")
                continue
        
    except Exception as e:
        print(f"    ❌ 新北市抓取失敗: {str(e)[:50]}")
    
    return new_articles

def write_to_hub(article):
    """寫入 Google Sheets"""
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    now = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    new_id = generate_id()
    
    row_to_add = [
        now,                          # A: 時間戳
        new_id,                       # B: 編號
        article['title'],             # C: 標題
        article['content'],          # D: 內文
        "地方",                       # E: 分類
        article['images'],            # F: 圖片
        "Pending",                    # G: 狀態
        "",                           # H: WP Link
        article['original_link'],    # I: Original Link
        "新北市政府"                  # J: 備註
    ]
    
    sheet.append_row(row_to_add, value_input_option='USER_ENTERED', insert_data_option='INSERT_ROWS')
    return new_id

# ============ 主程式 ============
def main():
    print("=" * 60)
    print("四合一情報偵查兵 - 新北市政府模組 (修正版)")
    print("=" * 60)
    
    print("\n[1] 抓取新北市政府新聞...")
    articles = scrape_ntpc_news()
    
    print(f"    共 {len(articles)} 篇新文章")
    
    if articles:
        print("\n[2] 寫入 Sheets...")
        for idx, a in enumerate(articles, 1):
            try:
                new_id = write_to_hub(a)
                print(f"    ✅ 已寫入: {new_id} - {a['title'][:30]}...")
            except Exception as e:
                print(f"    ❌ 寫入失敗: {str(e)[:30]}")
    
    print("\n" + "=" * 60)
    print("✅ 新北模組已修正，純文字內文與精確圖片排版已入稿")
    print("=" * 60)

if __name__ == "__main__":
    main()