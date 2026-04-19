import os
import requests
import datetime
import json
import re
from bs4 import BeautifulSoup
from openai import OpenAI

# ========= 配置 =========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

HEADERS = {"User-Agent": "Mozilla/5.0"}
NOW = datetime.datetime.now(datetime.timezone.utc)

# ========= 时间 =========
def within_7d(dt):
    return (NOW - dt).total_seconds() < 7 * 86400

# ========= 分类系统 =========
def classify(title):
    t = title.lower()

    if any(k in t for k in ["launchpool", "earn", "apr", "reward", "campaign", "bonus", "airdrop"]):
        return "活动"

    if any(k in t for k in ["launch", "listing", "lists"]):
        return "上币"

    if any(k in t for k in ["copy trading", "futures", "feature", "trading"]):
        return "产品"

    if any(k in t for k in ["partnership", "collaboration"]):
        return "品牌"

    if any(k in t for k in ["register", "license", "compliance"]):
        return "合规"

    return "其他"

# ========= 优先级 =========
def score(item):
    base = 1

    if item["category"] == "活动":
        base += 3
    if item["category"] == "上币":
        base += 2
    if item["category"] == "产品":
        base += 2

    return base

# ========= 抓取 =========
def fetch_bitget():
    url = "https://www.bitget.com/blog"
    html = requests.get(url, headers=HEADERS).text
    soup = BeautifulSoup(html, "html.parser")

    results = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/blog/articles/" not in href:
            continue

        title = a.get_text(strip=True)
        if len(title) < 15:
            continue

        link = "https://www.bitget.com" + href

        parent_text = a.parent.get_text(" ", strip=True)

        match = re.search(r"\d{4}-\d{2}-\d{2}", parent_text)
        if not match:
            continue

        dt = datetime.datetime.strptime(match.group(), "%Y-%m-%d")
        dt = dt.replace(tzinfo=datetime.timezone.utc)

        if not within_7d(dt):
            continue

        category = classify(title)

        results.append({
            "exchange": "Bitget",
            "title": title,
            "link": link,
            "published_at": match.group(),
            "category": category
        })

    # 去重
    unique = {x["link"]: x for x in results}

    # 排序（重要）
    sorted_items = sorted(unique.values(), key=score, reverse=True)

    return sorted_items[:6]

# ========= AI =========
def generate_report(items):
    raw = json.dumps(items, ensure_ascii=False, indent=2)

    prompt = f"""
你是加密交易所竞品分析师。

以下是Bitget过去7天真实Blog数据（含标题+时间+链接）：

{raw}

严格要求：

1. 只能基于数据分析，不允许编造
2. 每条结论必须引用原始link
3. 不允许扩展未提供信息
4. 不允许出现Bitget以外交易所
5. 分类优先级：活动 > 上币 > 产品 > 其他

输出结构：

【Bitget核心动态】
（1条最重要，必须带link）

【关键动作拆解】
（3-5条，每条带link）

【LBank可执行建议】
（必须结合以上动作）

输出要像专业周报
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
    print("抓取Bitget...")
    items = fetch_bitget()

    print("AI分析...")
    report = generate_report(items)

    print("发送...")
    send_to_lark(report)

    print("完成")

if __name__ == "__main__":
    main()
