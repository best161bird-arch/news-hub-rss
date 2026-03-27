import warnings
#!/usr/bin/env python3
"""
三合一情報偵查兵 - external_scout.py (輕量化版)
"""

import os
import re
import json
import requests
import gspread
import feedparser
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import time
import random
import urllib3

urllib3.disable_warnings()
warnings.filterwarnings('ignore')

# ============ 環境變數 ============
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

# ============ 時區 ============
TAIPEI_TZ = timezone(timedelta(hours=8))

# ============ Headers ============
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

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

def get_existing_titles():
    """取得現有標題 (C欄)"""
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    all_values = sheet.get_all_values()
    titles = set()
    for row in all_values[1:]:
        if len(row) >= 3 and row[2].strip():  # C欄 = 標題
            titles.add(row[2].strip())
    return titles

def write_to_hub(title, content, category, images, source="", original_link=""):
    """
    寫入 Google Sheets (A-J 架構)
    A: 時間戳 | B: 編號 | C: 標題 | D: 內文 | E: 分類 | F: 圖片 | G: 狀態 | H: WP Link | I: Original Link | J: 備註
    """
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    now = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    # 產生編號
    last_row = len(sheet.get_all_values())
    new_id = last_row
    # G欄=Pending
    row_to_add = [now, new_id, title, content, category, images, "Pending", "", original_link, ""]
    sheet.append_row(row_to_add, value_input_option='USER_ENTERED', insert_data_option='INSERT_ROWS')
    return True

# ============ 苗栗縣府 (RSS) ============
def extract_miaoli_images(html_content):
    images = []
    soup = BeautifulSoup(html_content, 'html.parser')
    fancybox = soup.select('a.fancybox-buttons')
    for link in fancybox:
        href = link.get('href', '')
        if href and any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png']):
            if '@' not in href and 'thumb' not in href.lower():
                images.append(href)
    if not images:
        imgs = soup.select('img')
        for img in imgs:
            src = img.get('src', '')
            if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png']):
                clean = src.split('@')[0].split('?')[0]
                if 'thumb' not in clean.lower():
                    images.append(clean)
    return images[:5]

# ============ MiniMax AI 標題改寫函數 ============
def rewrite_title_with_ai(title, region="苗栗"):
    """使用 MiniMax API 將標題改寫為更吸引人的版本"""
    import requests
    
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        return f"【{region}】{title}"
    
    prompt = f"""請將以下新聞標題改寫得更適合網路傳播。

要求：
1. 保持原意但更簡潔有力
2. 自動移除「【代發...新聞稿】」等冗餘詞彙
3. 加上地域標籤如【{region}】
4. 用繁體中文

原文標題：{title}

請直接輸出改寫後的標題，不要有其他說明。"""

    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "abab6.5-chat",
        "messages": [
            {"role": "system", "content": "你是一位專業的新聞編輯，擅長改寫新聞標題。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            rewritten = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            if rewritten:
                # 確保包含正確的地域標籤
                if f"【{region}】" not in rewritten:
                    rewritten = f"【{region}】{rewritten}"
                print(f"      ✅ 標題改寫: {title[:15]}... -> {rewritten[:15]}...")
                return rewritten
    except:
        pass
    
    return f"【{region}】{title}"

# ============ MiniMax AI 內容重組函數 ============
def rewrite_with_ai(content):
    """使用 MiniMax API 將內容改寫為 3-5 個重點摘要"""
    import requests
    import json
    
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        print("      ⚠️ MINIMAX_API_KEY 未設定，使用原文")
        return content
    
    prompt = f"""請將以下新聞內容改寫為精簡的繁體中文摘要。

要求：
1. 自動過濾掉文末的聯絡人姓名、電話號碼、電子郵件、傳真號碼、行政編號、地址等非新聞資訊
2. 只保留實質新聞內容
3. 濃縮為 100-200 字的流暢段落摘要
4. 使用專業新聞報導風格
5. 用繁體中文

新聞內容：
{content[:3000]}
"""
    
    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "abab6.5-chat",
        "messages": [
            {"role": "system", "content": "你是一位專業的新聞編輯，擅長將新聞內容改寫為簡潔有力的摘要。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            rewritten = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            if rewritten:
                print("      ✅ MiniMax AI 內容重組完成")
                return rewritten
        else:
            print(f"      ⚠️ MiniMax API 錯誤: {response.status_code}")
    except Exception as e:
        print(f"      ⚠️ MiniMax 重組失敗: {str(e)[:30]}")
    
    return content

# ============ 苗栗縣府 (RSS) + MiniMax AI ============
def scout_miaoli():
    print("\n[1] 偵察苗栗縣政府 RSS (MiniMax AI 改寫模式)...")
    url = "https://www.miaoli.gov.tw/OpenData.aspx?SN=F871C7470FAF2E95"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        feed = feedparser.parse(response.text)
        articles = []
        for entry in feed.entries[:10]:
            title = entry.get('title', '').strip()
            description = entry.get('summary', '')
            images = extract_miaoli_images(description)
            soup = BeautifulSoup(description, 'html.parser')
            content = soup.get_text()
            
            if title:
                # MiniMax 標題改寫 (苗栗)
                new_title = rewrite_title_with_ai(title, "苗栗")
                # MiniMax 內容改寫
                new_content = rewrite_with_ai(content)
                
                articles.append({
                    'title': new_title,
                    'content': new_content,
                    'images': ', '.join(images)
                })
        print(f"    找到 {len(articles)} 篇")
        return articles
    except Exception as e:
        print(f"    ❌ 錯誤: {str(e)[:50]}")
        return []

# ============ 台中市政府 Web Scraping + AI 極簡採編 ============
def scout_taichung():
    print("\n[2] 偵察台中市政府 Web (AI 極簡模式)...")
    url = "https://www.taichung.gov.tw/9962/Lpsimplelist"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    try:
        # 1. 抓取列表 (忽略 SSL, 設定編碼)
        resp = requests.get(url, headers=headers, verify=False, timeout=20)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 2. 定位新聞連結 (只取最新的前 3 則以維持速度)
        table = soup.select_one('table[summary]')
        if table:
            links = table.select('a')[:3]
        else:
            links = soup.select('.lp_table a[href*="post"]')[:3]
        
        print(f"    台中偵察發現了 {len(links)} 個連結")
        
        articles = []
        for idx, link in enumerate(links, 1):
            title = link.get_text(strip=True)
            if not title:
                continue
            
            detail_url = "https://www.taichung.gov.tw" + link['href'] if not link['href'].startswith('http') else link['href']
            print(f"    正在進入第 {idx} 個: {title[:20]}...")
            
            # 3. 進入內頁抓取
            detail_resp = requests.get(detail_url, headers=headers, verify=False, timeout=15)
            detail_resp.encoding = 'utf-8'
            detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
            
            # 【精準抓取】內文容器鎖定：article#cpArticle
            content_elem = detail_soup.select_one('article#cpArticle')
            if not content_elem:
                content_elem = detail_soup.select_one('#cpArticle')
            if not content_elem:
                content_elem = detail_soup.select_one('.cp')
            
            raw_content = content_elem.get_text('\n', strip=True) if content_elem else ""
            
            # 4. 【AI 自動轉化】將原始內文交由 AI 處理
            print("      正在進行 AI 內容重組...")
            ai_content = rewrite_with_ai(raw_content)
            
            # 5. 【高畫質圖片還原 + 黑名單過濾】
            # 黑名單網址排除
            blacklist = [
                '市府header.png',
                '市府header.jpg',
                '市府header.jpeg',
                'QR-Code',
                'qr-code',
                'line-qr-code',
                '無障礙a.jpg',
                'egov.gif',
                'QRcode',
                'qrcode'
            ]
            
            # 優先從內文區塊抓取圖片
            content_imgs = []
            if content_elem:
                content_imgs = content_elem.select('img')
            
            full_imgs = []
            for img in content_imgs:
                img_src = img.get('src', '')
                if not img_src:
                    continue
                
                # 跳過黑名單
                if any(b in img_src for b in blacklist):
                    continue
                    
                clean_path = img_src.split('?')[0]
                full_url = "https://www.taichung.gov.tw" + clean_path if clean_path.startswith('/') else clean_path
                
                # 簡單過濾：只接受 /media/ 開頭的新聞圖片
                if '/media/' in full_url and full_url not in full_imgs:
                    full_imgs.append(full_url)
            
            # 如果內文區塊沒圖片，才抓全域的 /media/ 圖片
            if not full_imgs:
                raw_imgs = [img['src'] for img in detail_soup.select('img') if '/media/' in img.get('src', '')]
                for img_path in raw_imgs:
                    if any(b in img_path for b in blacklist):
                        continue
                    clean_path = img_path.split('?')[0]
                    full_url = "https://www.taichung.gov.tw" + clean_path if clean_path.startswith('/') else clean_path
                    if full_url not in full_imgs:
                        full_imgs.append(full_url)
            
            # 6. 【標題標籤化】
            # 移除【代發...新聞稿】並加上【台中】前綴
            clean_title = title.replace('【代發', '').replace('代發', '').replace('新聞稿', '').replace('】', '').replace('【', '').strip()
            final_title = f"【台中】{clean_title}"
            
            if final_title:
                articles.append({
                    'title': final_title,
                    'content': ai_content,
                    'images': ', '.join(full_imgs[:5]),
                    'original_link': detail_url  # I欄
                })
        
        print(f"    找到 {len(articles)} 篇")
        return articles
    except Exception as e:
        print(f"    ❌ 台中抓取錯誤: {str(e)[:50]}")
        return []

# ============ 基隆市政府 (Web) - 前3則, timeout=20 ============
def scout_keelung():
    print("\n[3] 偵察基隆市政府 Web...")
    list_url = "https://www.klcg.gov.tw/tw/klcg1/3168.html"
    try:
        response = requests.get(list_url, headers=HEADERS, timeout=20, verify=False)
        # 強制設定 UTF-8 編碼，解決標題亂碼
        response.encoding = 'utf-8'
        if not response.text[:5000].encode('utf-8').decode('utf-8'):
            response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = soup.select('div.list_block a, ul.list_block a, .list_block a, .list_text a')
        
        print(f"    基隆偵察發現了 {len(news_items)} 個連結")
        
        articles = []
        for idx, item in enumerate(news_items[:3], 1):
            link = item.get('href', '')
            title = item.get_text(strip=True)
            if not title or not link:
                continue
            print(f"    正在進入第 {idx} 個: {title[:20]}...")
            
            # 補全網址
            if not link.startswith('http'):
                link = 'https://www.klcg.gov.tw' + link
            
            try:
                time.sleep(1)
                detail_response = requests.get(link, headers=HEADERS, timeout=20, verify=False)
                # 強制設定 UTF-8 編碼
                detail_response.encoding = 'utf-8'
                if not detail_response.text[:5000].encode('utf-8').decode('utf-8'):
                    detail_response.encoding = detail_response.apparent_encoding
                detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                
                # 精準提取內文：優先抓取 .cp 或 .article_content 類別
                content_area = detail_soup.select('.cp, .article_content, #content_box, .content')
                content = content_area[0].get_text(strip=True) if content_area else ''
                
                # 圖片特徵過濾：僅抓取 /public/Attachment/ 的圖片
                images = []
                imgs = detail_soup.select('img')
                for img in imgs:
                    src = img.get('src', '')
                    # 過濾條件：
                    # 1. 排除 icon_、basic、styles
                    if any(x in src.lower() for x in ['icon_', '/basic/', '/styles/']):
                        continue
                    # 2. 僅抓取包含 /public/Attachment/ 的圖片
                    if '/public/attachment/' in src.lower():
                        # 補全網址
                        if not src.startswith('http'):
                            src = 'https://www.klcg.gov.tw' + src
                        images.append(src)
                
                if title:
                    # MiniMax 標題改寫 (基隆)
                    new_title = rewrite_title_with_ai(title, "基隆")
                    # MiniMax 內容改寫
                    new_content = rewrite_with_ai(content[:2000])
                    
                    articles.append({
                        'title': new_title,
                        'content': new_content,
                        'images': ', '.join(images[:5]),
                        'original_link': link
                    })
            except Exception as e:
                print(f"      ⚠️ 內頁錯誤: {str(e)[:30]}")
                continue
        
        print(f"    找到 {len(articles)} 篇")
        return articles
    except Exception as e:
        print(f"    ❌ 錯誤: {str(e)[:50]}")
        return []


# ============ 高雄市政府 Web Scraping + Playwright (Agent Reach) ============
def scout_kaohsiung():
    print("\n[4] 偵察高雄市政府 Web (Playwright 模式)...")
    from playwright.sync_api import sync_playwright
    
    url = "https://www.kcg.gov.tw/CityNews.aspx?n=29"
    
    try:
        with sync_playwright() as p:
            # 啟動 Chromium (headless)
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            page.set_default_timeout(45000)  # 45秒 timeout
            
            print(f"    正在開啟: {url}")
            page.goto(url, wait_until='domcontentloaded')
            
            # 等待新聞列表區塊
            try:
                page.wait_for_selector('.news-list, .CityNewsList, table tbody tr', timeout=15000)
                print("    ✅ 新聞列表已渲染")
            except:
                print("    ⚠️ 等待 selector逾時，但繼續抓取")
            
            # 模擬隨機滾動 (避開機器人偵測)
            for _ in range(3):
                page.mouse.wheel(0, 300)
                page.wait_for_timeout(500)
            
            # 抓取新聞連結
            links = page.query_selector_all('a[href*="CityNews_Detail1.aspx"]')[:3]
            print(f"    高雄偵察發現了 {len(links)} 個連結")
            
            articles = []
            for idx, link in enumerate(links, 1):
                try:
                    raw_title = link.inner_text().strip()
                    if not raw_title:
                        continue
                    
                    print(f"    正在進入第 {idx} 個: {raw_title[:20]}...")
                    
                    # 標題清洗
                    clean_title = re.sub(r'【代發.*?新聞稿】', '', raw_title).strip()
                    clean_title = re.sub(r'【代發.*?】', '', clean_title).strip()
                    final_title = f"【高雄】{clean_title}"
                    
                    # 取得連結
                    href = link.get_attribute('href')
                    detail_url = "https://www.kcg.gov.tw/" + href if not href.startswith('http') else href
                    
                    # 進入內頁
                    detail_page = context.new_page()
                    detail_page.goto(detail_url, wait_until='domcontentloaded', timeout=30000)
                    
                    # 提取內文
                    try:
                        detail_page.wait_for_selector('.p-2, .article_content, .content', timeout=10000)
                    except:
                        pass
                    
                    content_node = detail_page.query_selector('.p-2') or detail_page.query_selector('.article_content') or detail_page.query_selector('.content')
                    content = content_node.inner_text('\n', strip=True) if content_node else ""
                    
                    # 提取圖片
                    imgs = detail_page.query_selector_all('img[src*="RelPic"]')
                    unique_imgs = []
                    for img in imgs:
                        img_url = img.get_attribute('src')
                        if img_url:
                            full_url = img_url if img_url.startswith('http') else "https://www.kcg.gov.tw" + img_url
                            if full_url not in unique_imgs:
                                unique_imgs.append(full_url)
                    
                    detail_page.close()
                    
                    if final_title and content:
                        # MiniMax 內容改寫
                        new_content = rewrite_with_ai(content[:2000])
                        
                        articles.append({
                            'title': final_title,
                            'content': new_content,
                            'images': ', '.join(unique_imgs[:5]),
                            'original_link': detail_url
                        })
                        print(f"      ✅ 完成: {final_title[:30]}...")
                        
                except Exception as e:
                    print(f"      ⚠️ 內頁錯誤: {str(e)[:30]}")
                    continue
            
            browser.close()
            
        print(f"    找到 {len(articles)} 篇")
        return articles
        
    except Exception as e:
        print(f"    ❌ 高雄抓取錯誤: {str(e)[:50]}")
        return []


# ============ 主程式 ============
def main():
    print("=" * 50)
    print("三合一情報偵查兵 (輕量化版)")
    print("=" * 50)
    
    print("\n[0] 檢查現有標題...")
    existing_titles = get_existing_titles()
    print(f"    現有標題數: {len(existing_titles)}")
    
    all_articles = []
    
    # 三個來源
    for article in scout_miaoli():
        article['source'] = '苗栗'
        all_articles.append(article)
    
    for article in scout_taichung():
        article['source'] = '台中'
        all_articles.append(article)
    
    for article in scout_keelung():
        article['source'] = '基隆'
        all_articles.append(article)
    
    # for article in scout_kaohsiung():  # 高雄已禁用
    #     article['source'] = '高雄'
    #     all_articles.append(article)
    
    # 防重
    print("\n[4] 防重檢查...")
    new_articles = []
    for article in all_articles:
        if article['title'] not in existing_titles:
            new_articles.append(article)
            existing_titles.add(article['title'])
    
    print(f"    新增文章: {len(new_articles)}")
    
    # 寫入
    print("\n[5] 寫入 Google Sheets...")
    for article in new_articles:
        try:
            original_link = article.get('original_link', '')
            write_to_hub(article['title'], article['content'], '地方', article['images'], article['source'], original_link)
            print(f"    ✅ {article['source']}: {article['title'][:30]}...")
        except Exception as e:
            print(f"    ❌ 寫入失敗: {str(e)}")
    
    print("\n" + "=" * 50)
    print("偵察兵任務完成")
    print("=" * 50)

# ============ WordPress 狀態同步 ============
def sync_wp_status():
    """
    WordPress 狀態巡檢 (每小時執行)
    - 搜尋 WordPress 文章標題
    - 若匹配成功，更新 G 欄為 'Published' 並將連結填入 H 欄
    """
    print("\n" + "=" * 50)
    print("WordPress 狀態同步開始")
    print("=" * 50)
    
    wp_url = os.getenv("WORDPRESS_URL")
    wp_user = os.getenv("WORDPRESS_USER")
    wp_app_password = os.getenv("WORDPRESS_APP_PASSWORD")
    
    if not all([wp_url, wp_user, wp_app_password]):
        print("⚠️ WordPress 環境變數未設定")
        return
    
    # 取得 Google Sheets 中的 Pending 文章
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    all_rows = sheet.get_all_values()
    
    print(f"\n[1] 檢查 {len(all_rows)-1} 筆資料...")
    
    # 從 WordPress 取得已發布文章
    auth = (wp_user, wp_app_password)
    wp_posts_url = f"{wp_url}/wp-json/wp/v2/posts?per_page=100"
    
    try:
        wp_response = requests.get(wp_posts_url, auth=auth, timeout=30)
        if wp_response.status_code != 200:
            print(f"⚠️ WP API 錯誤: {wp_response.status_code}")
            return
        
        wp_posts = wp_response.json()
        wp_titles = {post['title']['rendered'].strip(): post['link'] for post in wp_posts}
        print(f"    WordPress 共有 {len(wp_titles)} 篇已發布文章")
        
        # 比對並更新 (檢查 Pending, Approved, Empty 狀態)
        updated_count = 0
        for row_idx, row in enumerate(all_rows[1:], start=2):  # 從第2行開始
            if len(row) >= 8:
                status = row[6] if len(row) > 6 else ""  # G欄
                # 只更新尚未發布的狀態
                if status in ["Pending", "Approved", "", "Empty"]:
                    title = row[2] if len(row) > 2 else ""  # C欄
                    if title and title in wp_titles:
                        wp_link = wp_titles[title]
                        # 更新 G欄=Published, H欄=WP Link
                        sheet.update_cell(row_idx, 7, "Published")  # G欄
                        sheet.update_cell(row_idx, 8, wp_link)      # H欄
                        print(f"    ✅ 已發布: {title[:30]}...")
                        updated_count += 1
        
        print(f"\n[2] 完成 - 更新 {updated_count} 篇文章狀態")
        
    except Exception as e:
        print(f"⚠️ WordPress 同步錯誤: {str(e)[:50]}")
    
    print("\n" + "=" * 50)
    print("WordPress 狀態同步完成")
    print("=" * 50)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--sync-wp":
        sync_wp_status()
    else:
        main()
