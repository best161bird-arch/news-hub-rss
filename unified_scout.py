#!/usr/bin/env python3
"""
四合一情報偵察整合腳本 (Unified Runner)
執行四個獨立模組 + GitHub 推送 + Telegram 回報
"""
import os
import json
import subprocess
import sys
from datetime import datetime
import urllib.parse

LOG_FILE = "/home/node/.openclaw/workspace/logs/scout_cron.log"
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")

def load_env():
    """Load .env file and set environment variables"""
    env_file = "/home/node/.openclaw/workspace/.env"
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

def run_script(script_path, desc):
    """Run a Python script with error handling"""
    log(f"開始執行: {desc}")
    try:
        result = subprocess.run(
            ['/home/node/.linuxbrew/bin/python3', script_path],
            capture_output=True,
            text=True,
            timeout=180,
            cwd="/home/node/.openclaw/workspace"
        )
        if result.returncode == 0:
            log(f"✅ {desc} 完成")
            return True, result.stdout
        else:
            log(f"⚠️ {desc} 有警告: {result.stderr[:200] if result.stderr else 'N/A'}")
            return True, result.stdout
    except Exception as e:
        log(f"❌ {desc} 失敗: {str(e)}")
        return False, str(e)

def git_push():
    """執行 Git add, commit, push"""
    log("執行 Git 推送...")
    try:
        # Add all changes
        subprocess.run(['git', 'add', '-A'], cwd="/home/node/.openclaw/workspace", capture_output=True)
        
        # Commit with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Auto-sync: {timestamp}"
        subprocess.run(['git', 'commit', '-m', commit_msg], cwd="/home/node/.openclaw/workspace", capture_output=True)
        
        # Push
        result = subprocess.run(
            ['git', 'push', 'origin', 'master'],
            cwd="/home/node/.openclaw/workspace",
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            log("✅ Git 推送成功")
            return True, ""
        else:
            error_msg = result.stderr if result.stderr else f"Error code: {result.returncode}"
            log(f"❌ Git 推送失敗: {error_msg}")
            return False, error_msg
    except Exception as e:
        error_msg = str(e)
        log(f"❌ Git 推送失敗: {error_msg}")
        return False, error_msg

def get_sheet_stats():
    """取得 Google Sheets 統計數據"""
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        
        GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
        GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        
        if isinstance(GOOGLE_SHEETS_CREDENTIALS, dict):
            creds_json = GOOGLE_SHEETS_CREDENTIALS
        else:
            creds_json = json.loads(GOOGLE_SHEETS_CREDENTIALS)
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1
        all_values = sheet.get_all_values()
        
        total = len(all_values) - 1  # 扣除標題列
        
        # 統計各城市數量
        city_counts = {}
        for row in all_values[1:]:
            if len(row) >= 10:
                city = row[9].strip() if row[9] else "未知"
                city_counts[city] = city_counts.get(city, 0) + 1
        
        return total, city_counts
    except Exception as e:
        log(f"⚠️ 取得統計失敗: {str(e)}")
        return 0, {}

def send_telegram_report(miaoli_count, taichung_count, keelung_count, ntpc_count, git_success, git_error):
    """發送 Telegram 報告"""
    try:
        import requests
        
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            log("⚠️ 缺少 Telegram 設定")
            return
        
        total = miaoli_count + taichung_count + keelung_count + ntpc_count
        
        # 表格內容
        table = """📊 <b>情報偵查報告</b>

| 縣市 | 新增數 |
|------|--------|
| 苗栗 (RSS) | """ + str(miaoli_count) + """ |
| 台中 (Web) | """ + str(taichung_count) + """ |
| 基隆 (Web) | """ + str(keelung_count) + """ |
| 新北 (NTPC) | """ + str(ntpc_count) + """ |
| <b>總計</b> | <b>""" + str(total) + """</b> |

"""
        
        git_status = "✅ Git 推送成功" if git_success else f"❌ Git 推送失敗: {git_error}"
        table += f"🔄 {git_status}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": table,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            log("📱 Telegram 報告已發送")
        else:
            log(f"⚠️ Telegram 發送失敗: {response.status_code}")
    
    except Exception as e:
        log(f"⚠️ Telegram 回報失敗: {str(e)}")

def main():
    log("=== 四合一情報偵查報告開始 ===")
    
    # Load environment
    load_env()
    
    # 執行四個獨立模組
    miaoli_success, miaoli_out = run_script("/home/node/.openclaw/workspace/scout_miaoli.py", "scout_miaoli.py (苗栗 RSS)")
    taichung_success, taichung_out = run_script("/home/node/.openclaw/workspace/scout_taichung.py", "scout_taichung.py (台中 Web)")
    keelung_success, keelung_out = run_script("/home/node/.openclaw/workspace/scout_keelung.py", "scout_keelung.py (基隆 Web)")
    ntpc_success, ntpc_out = run_script("/home/node/.openclaw/workspace/external_scout_ntpc.py", "scout_ntpc.py (新北 Web)")
    
    # 解析輸出以取得新增數量
    miaoli_count = miaoli_out.count("✅ 已寫入") if miaoli_out else 0
    taichung_count = taichung_out.count("✅ 已寫入") if taichung_out else 0
    keelung_count = keelung_out.count("✅ 已寫入") if keelung_out else 0
    ntpc_count = ntpc_out.count("✅ 已寫入") if ntpc_out else 0
    
    # 執行 RSS 產生器
    rss_success, rss_out = run_script("/home/node/.openclaw/workspace/rss_generator.py", "RSS 產生器")
    
    # 執行 Git push
    git_success, git_error = git_push()
    
    # 發送 Telegram 報告
    send_telegram_report(miaoli_count, taichung_count, keelung_count, ntpc_count, git_success, git_error)
    
    log("=== 四合一情報偵查報告完成 ===")

if __name__ == "__main__":
    main()
