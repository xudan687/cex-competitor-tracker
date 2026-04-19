import os
import requests
import datetime
import json
from openai import OpenAI

# ========= 配置 =========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

if not DEEPSEEK_API_KEY:
    raise ValueError("Missing DEEPSEEK_API_KEY")

if not LARK_WEBHOOK:
    raise ValueError("Missing LARK_WEBHOOK")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

NOW = datetime.datetime.now(datetime.timezone.utc)

# ========= 时间 =========
def within_7d(dt):
    return (NOW - dt).total_seconds() < 7 * 86400

# ========= 分类 =========
def classify(title):
    t = title.lower()

    if any(k in t for k in ["campaign", "reward", "bonus", "airdrop", "earn"]):
        return "活动"

    if any(k in t for k in ["launch", "listing", "lists"]):
        return "上币"

    if any(k in t for k in ["trading", "futures", "copy"]):
        return "产品"

    if any(k in t for k in ["report", "fund"]):
        return "数据"

    return "其他"

# ========= 抓 Bitget（API版） =========
def fetch_bitget():
    url = "https://www.bitget.com/api/cms/articles?language=en_US&pageSize=20"

    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code != 200:
        print("❌ API请求失败:", resp.status_code)
        return []

    data = resp.json()

    items = []

    for item in data.get("data", []):
        title = item.get("title")
        article_id = item.get("id")
        publish_time = item.get("publishTime")

        if not title or not publish_time:
            continue

        # 转时间
        dt = datetime.datetime.fromtimestamp(
            publish_time / 1000,
            tz=datetime.timezone.utc
        )

        # 过滤7天
        if not within_7d(dt):
            continue

        # 正确链接（不会404）
        link = f"https://www.bitget.com/en/support/articles/{article_id}"

        items.append({
            "exchange": "Bitget",
            "title": title,
            "link": link,
            "published_at": dt.strftime("%Y-%m-%d"),
            "category": classify(title)
        })

    return items[:8]

# ========= AI =========
def generate_report(items):
    if not items:
        return "过去7天内未抓取到Bitget有效公告数据"

    raw = json.dumps(items, ensure_ascii=False, indent=2)

    prompt = f"""
你是加密交易所竞品分析师。

分析范围：过去7天
对象：Bitget

以下是官方真实数据：

{raw}

严格要求：

1. 只能基于数据分析，不允许编造
2. 每条结论必须附带 link
3. 不允许扩展未提供的信息
4. 输出：

【Bitget核心动态】
（1条最重要）

【关键动作拆解】
（3-5条）

【LBank可执行建议】

风格：简洁、像周报、可验证
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
    print("📡 抓取Bitget数据...")
    items = fetch_bitget()

    print("📊 抓取结果：")
    print(json.dumps(items, ensure_ascii=False, indent=2))

    print("🧠 AI分析...")
    report = generate_report(items)

    print("📨 发送到飞书...")
    send_to_lark(report)

    print("✅ 完成")

if __name__ == "__main__":
    main()
