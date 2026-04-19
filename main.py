import os
import requests
import datetime
from bs4 import BeautifulSoup
from openai import OpenAI
import json

# ========= 配置 =========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

HEADERS = {"User-Agent": "Mozilla/5.0"}

NOW = datetime.datetime.now(datetime.timezone.utc)

# ========= 时间过滤 =========

def within_7d(dt):
    return (NOW - dt).total_seconds() < 7 * 86400

# ========= 抓 Bitget Blog =========

def fetch_bitget_articles():
    url = "https://www.bitget.com/blog"
    html = requests.get(url, headers=HEADERS, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    articles = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/blog/articles/" not in href:
            continue

        link = "https://www.bitget.com" + href

        title = a.get_text(strip=True)

        # 简单过滤无效标题
        if len(title) < 10:
            continue

        articles.append({
            "exchange": "Bitget",
            "title": title,
            "link": link,
            "source": "official"
        })

    # 去重
    unique = {item["link"]: item for item in articles}

    return list(unique.values())[:10]


# ========= 抓详情页（补时间） =========

def enrich_with_time(items):
    results = []

    for item in items:
        try:
            html = requests.get(item["link"], headers=HEADERS, timeout=10).text
            soup = BeautifulSoup(html, "html.parser")

            text = soup.get_text()

            # 简单找日期（YYYY-MM-DD）
            import re
            match = re.search(r"\d{4}-\d{2}-\d{2}", text)

            if not match:
                continue

            dt = datetime.datetime.strptime(match.group(), "%Y-%m-%d")
            dt = dt.replace(tzinfo=datetime.timezone.utc)

            if not within_7d(dt):
                continue

            item["published_at"] = match.group()

            results.append(item)

        except:
            continue

    return results


# ========= AI分析 =========

def generate_report(items):
    today = NOW.strftime("%Y-%m-%d")

    raw = json.dumps(items, ensure_ascii=False, indent=2)

    prompt = f"""
你是加密交易所竞品分析师。

当前时间：{today}
分析范围：过去7天

以下是Bitget官方Blog数据：

{raw}

要求：

1. 只基于这些数据分析，不允许编造
2. 提炼：
   - 1个最重要动态
   - 其他关键动作
3. 每条结论必须对应原始title
4. 输出：

【Bitget核心动态】
【关键动作拆解】
【LBank可执行建议】

5. 如果数据不足，直接说明
"""

    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return res.choices[0].message.content


# ========= 飞书 =========

def send_to_lark(text):
    requests.post(LARK_WEBHOOK, json={
        "msg_type": "text",
        "content": {"text": text}
    })


# ========= 主 =========

def main():
    print("抓Bitget列表...")
    articles = fetch_bitget_articles()

    print("解析时间...")
    articles = enrich_with_time(articles)

    print("AI分析...")
    report = generate_report(articles)

    print("发送...")
    send_to_lark(report)

    print("完成")


if __name__ == "__main__":
    main()
