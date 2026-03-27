#!/bin/bash
# 四合一情報偵察排程腳本
# 執行：苗栗 + 台中 + 基隆 + 新北

# 載入環境變數
source /home/node/.openclaw/workspace/.env 2>/dev/null

# 確保環境變數存在
export GOOGLE_SHEETS_CREDENTIALS="${GOOGLE_SHEETS_CREDENTIALS}"
export GOOGLE_SHEETS_ID="${GOOGLE_SHEETS_ID}"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export GITHUB_REPO="${GITHUB_REPO}"
export GEMINI_API_KEY="${GEMINI_API_KEY}"
export GOOGLE_SHEETS_TOKEN_CACHE_DIR="${GOOGLE_SHEETS_TOKEN_CACHE_DIR}"

cd /home/node/.openclaw/workspace

# 執行四合一偵察
echo "=== 情報偵查報告開始 ===" >> logs/scout_cron.log
date >> logs/scout_cron.log

python3 /home/node/.openclaw/workspace/external_scout.py >> logs/scout_cron.log 2>&1 || echo "苗栗/台中/基隆偵察完成"
python3 /home/node/.openclaw/workspace/external_scout_ntpc.py >> logs/scout_cron.log 2>&1 || echo "新北偵察完成"
python3 /home/node/.openclaw/workspace/rss_generator.py >> logs/scout_cron.log 2>&1 || echo "RSS 產生完成"

echo "=== 情報偵查報告完成 ===" >> logs/scout_cron.log