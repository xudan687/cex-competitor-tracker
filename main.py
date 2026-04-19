import os
import requests
import datetime
import feedparser
from dateutil import parser
from openai import OpenAI

# ========= 配置 =========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

NOW = datetime.datetime.utcnow()

# ========= 时间过滤 =========

def within_24h(dt):
    return (NOW - dt).total_seconds() < 86400

# ========= 标签系统 =========

def tag_content(text):
    text = text.lower()
    if "launch" in text or "listing" in text:
        return "上币"
    if "campaign" in text or "reward" in text:
        return "活动"
    if "partnership" in text:
        return "品牌"
    return "其他"

# ========= RSS抓取（核心） =========

def fetch_rss(name, url):
    feed = feedparser.parse(url)
    results = []

    for entry in feed.entries[:10]:
        try:
            dt = parser.parse(entry.published)
        except:
            continue

        if not within_24h(dt):
            continue

        title = entry.title
        link = entry.link
        tag = tag_content(title)

        results.append(f"[{name}][{tag}]\n{title}\n{link}")

    return results

# ========= 官方源 =========

def fetch_official():
    data = []

    # Bybit 官方
    data += fetch_rss("Bybit", "https://www.bybit.com/en/press/rss")

    # MEXC（无RSS，用fallback）
    try:
        html = requests.get("https://www.mexc.com/announcements/latest-events").text
        if "2026" in html:
            data.append("[MEXC][活动]\n最新公告页\nhttps://www.mexc.com/announcements/latest-events")
    except:
        pass

    return data

# ========= 媒体源（高优先级） =========

def fetch_media():
    data = []

    KEYWORDS = ["bybit", "okx", "bitget", "mexc", "gate"]

    for kw in KEYWORDS:
        url = f"https://cointelegraph.com/rss/tag/{kw}"

        data += fetch_rss(f"Media-{kw}", url)

    return data

# ========= 汇总 =========

def collect_data():
    data = []

    data += fetch_official()
    data += fetch_media()

    return "\n\n".join(data)

# ========= AI分析 =========

def generate_report(raw):
    today = NOW.strftime("%Y-%m-%d")

    prompt = f"""
你是加密交易所竞品分析师。

当前时间：{today}
分析范围：过去24小时

以下是结构化数据：

{raw}

要求：

1. 只基于数据分析
2. 每家交易所提炼1个最大动态
3. 按交易所拆解
4. 输出：

【竞品核心动态】
【逐家拆解】
【LBank可执行建议】

5. 媒体来源权重更高
6. 不允许编造
"""

    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
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
    print("抓取数据...")
    raw = collect_data()

    print("AI分析...")
    report = generate_report(raw)

    print("发送...")
    send_to_lark(report)

    print("完成")

if __name__ == "__main__":
    main()
