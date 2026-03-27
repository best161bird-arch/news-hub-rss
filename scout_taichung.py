#!/usr/bin/env python3
"""
台中市偵察兵 - scout_taichung.py
獨立運作，去重邏輯內建，標準模式
"""
import os
import json
import re
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import warnings
import urllib3

warnings.filterwarnings('ignore')
urllib3.disable_warnings()

# 環境變數
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
TAIPEI_TZ = timezone(timedelta(hours=8))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_gs_client():
    if isinstance(GOOGLE_SHEETS_CREDENTIALS, dict):
        creds_json = GOOGLE_SHEETS_CREDENTIALS
    else:
        creds_json = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

def get_existing_ids():
    """取得現有 ID (A欄) 避免重複"""
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    all_values = sheet.get_all_values()
    return set(row[0] for row in all_values[1:] if row and row[0])

def get_existing_links():
    """取得現有原始連結 (I欄) 避免重複"""
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    all_values = sheet.get_all_values()
    return set(row[8] for row in all_values[1:] if len(row) > 8 and row[8])

def write_to_hub(title, content, category, images, source, original_link):
    """寫入 Google Sheets"""
    client = get_gs_client()
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
    
    timestamp = datetime.now(TAIPEI_TZ).strftime("%Y%m%d%H%M")
    row_id = f"GOV-TAICHUNG-{timestamp}"
    
    # 去重檢查 - ID
    existing_ids = get_existing_ids()
    if row_id in existing_ids:
        return False
    
    # 去重檢查 - 連結
    existing_links = get_existing_links()
    if original_link and original_link in existing_links:
        return False
    
    # 寫入
    row = [
        row_id,           # A: ID
        "",               # B: 狀態
        title,            # C: 標題
        content,          # D: 內文
        category,         # E: 分類
        images if images else "",  # F: 圖片
        "",               # G: 作者
        source,           # H: 來源
        original_link,    # I: 原始連結
        "台中",           # J: 城市
        datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S"),  # K: 日期
        "",               # L: 備註
    ]
    sheet.append_row(row)
    return True

def scout_taichung():
    """偵察台中市政府 Web"""
    print("[2] 偵察台中市政府 Web (標準模式)...")
    
    # 台中市新聞列表頁面
    base_url = "https://www.taichung.gov.tw"
    news_url = "https://www.taichung.gov.tw/API/Services/Public/DM/NewsTopList?deptcode=A00100&page=1&pageSize=20"
    
    try:
        resp = requests.get(news_url, headers=HEADERS, timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"    ⚠️ API 請求失敗: {e}")
        return 0
    
    news_list = data.get('Data', [])
    print(f"    發現 {len(news_list)} 個連結")
    
    count = 0
    for item in news_list[:5]:
        title = item.get('Title', '').strip()
        link = item.get('Url', '')
        if not title:
            continue
        
        full_link = base_url + link if link.startswith('/') else link
        
        # 簡單內容
        content = f"報新聞/編輯部\n\n標題：{title}\n\n新聞來源：台中市政府"
        
        if write_to_hub(title, content, "地方", "", "台中市政府", full_link):
            print(f"    ✅ 已寫入: {title[:25]}...")
            count += 1
    
    print(f"    台中新增: {count} 篇")
    return count

if __name__ == "__main__":
    scout_taichung()