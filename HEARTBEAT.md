# HEARTBEAT.md

## 每小時自動執行任務

### 任務零：情報偵查報告 (每小時，較 RSS 早 15 分鐘)

**執行頻率：** ✅ 已自動排程 (Hourly, 07-22, 每小時第3分鐘)

**要執行的動作：**
1. 執行 `python3 external_scout.py` (苗栗、台中、基隆)
2. 執行 `python3 external_scout_ntpc.py` (新北市)
3. 將新文章寫入 Google Sheets 01_採編審核

**狀態追蹤：**
- 記錄每次執行結果於 logs/external_scout.log

---

### 任務一：執行 RSS 產生器 (每小時)

**執行頻率：** ✅ 已自動排程 (Hourly, 07-22, 每小時第18分和第48分鐘)

**要執行的動作：**
1. 執行 `python3 rss_generator.py`
2. 將 Google Sheets 中狀態為 Approved 的文章推送到 GitHub RSS

**狀態追蹤：**
- 記錄每次執行結果於 logs/rss_generator.log

---

### 任務二：檢查苗栗縣政府 RSS (每小時)

**執行頻率：** 每 1 小時

**要執行的動作：**
1. 抓取 RSS: https://www.miaoli.gov.tw/OpenData.aspx?SN=F871C7470FAF2E95
2. 使用本地 LLM (Ollama llama3.2) 改寫標題和內容
3. 發布到 WordPress (分類: 地方)

**狀態追蹤：**
- 記錄已發布的文章連結避免重複發布
