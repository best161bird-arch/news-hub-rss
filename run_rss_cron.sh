#!/bin/bash
# RSS 產生器排程腳本

# 載入環境變數
source /home/node/.openclaw/workspace/.env 2>/dev/null

export GOOGLE_SHEETS_CREDENTIALS="${GOOGLE_SHEETS_CREDENTIALS}"
export GOOGLE_SHEETS_ID="${GOOGLE_SHEETS_ID}"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export GITHUB_REPO="${GITHUB_REPO}"
export GEMINI_API_KEY="${GEMINI_API_KEY}"
export GOOGLE_SHEETS_TOKEN_CACHE_DIR="${GOOGLE_SHEETS_TOKEN_CACHE_DIR}"

cd /home/node/.openclaw/workspace

echo "=== RSS 產生器開始 ===" >> logs/rss_cron.log
date >> logs/rss_cron.log

python3 rss_generator.py >> logs/rss_cron.log 2>&1

echo "=== RSS 產生器完成 ===" >> logs/rss_cron.log