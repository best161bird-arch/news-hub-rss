import json
import os
import requests

def rewrite_news(title, content):
    """使用 MiniMax API 將新聞改寫為精簡版本"""
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        print("⚠️ MINIMAX_API_KEY 未設定")
        return {"title": title, "content": content[:200]}
    
    prompt = f"""你是台灣專業新聞編輯。將以下新聞改寫成精簡版本（80-150字）。

要求：
1. 自動過濾掉文末的聯絡人姓名、電話號碼、電子郵件、傳真號碼、行政編號、地址等非新聞資訊
2. 使用專業新聞報導風格
3. 用繁體中文

原文標題：{title}
原文內容：{content}

輸出格式（JSON）：
{{"title": "改寫後標題", "content": "改寫後內容（80-150字）"}}"""

    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "abab6.5-chat",
        "messages": [
            {"role": "system", "content": "你是一位專業的新聞編輯，擅長將新聞內容改寫為簡潔有力的摘要，輸出必須是有效的JSON格式。"},
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
                # 嘗試解析 JSON
                try:
                    return json.loads(rewritten)
                except:
                    return {"title": title, "content": rewritten[:200]}
    except Exception as e:
        print(f"⚠️ MiniMax API 錯誤: {e}")
    
    return {"title": title, "content": content[:200]}

if __name__ == "__main__":
    # Test
    title = "三義分隊執行國道一號南下車禍救護案"
    content = "苗栗縣消防局三義分隊3月17日下午接獲派遣，國道一號南下154.8公里處砂石車翻覆，派遣救護車及消防車前往救援。現場1名患者有擦挫傷，生命徵象穩定。聯絡人：張隊長，電話：037-123456"
    
    result = rewrite_news(title, content)
    print(json.dumps(result, ensure_ascii=False))
