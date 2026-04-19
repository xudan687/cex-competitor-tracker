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

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ✅ 修复：统一为带时区 UTC
NOW = datetime.datetime.now(datetime.timezone.utc)

# ========= 时间处理 =========

def parse_time(entry):
    try:
        if hasattr(entry, "published"):
            dt = parser.parse(entry.published)
        elif hasattr(entry, "updated"):
            dt = parser.parse(entry.updated)
        else:
            return None

        # 统一UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)

        return dt
    except:
        return None


def within_24h(dt):
    if not dt:
        return False
    return (NOW - dt).total_seconds() < 86400


# ========= 标签系统 =========

def tag_content(text):
    text = text.lower()

    if any(k in text for k in ["launch", "listing"]):
        return "上币"

    if any(k in text for k in ["campaign", "reward", "event"]):
        return "活动"

    if any(k in text for k in ["partnership", "collaboration"]):
        return "品牌"

    return "其他"


# ========= RSS抓取 =========

def fetch_rss(name, url):
    feed = feedparser.parse(url)
    results = []

    for entry in feed.entries[:10]:
        dt = parse_time(entry)

        if not within_24h(dt):
            continue

        title = entry.title if hasattr(entry, "title") else ""
        link = entry.link if hasattr(entry, "link") else ""

        tag = tag_content(title)

        results.append(f"[{name}][{tag}]\n{title}\n{link}")

    return results


# ========= 官方源 =========

def fetch_official():
    data = []

    # ✅ Bybit 官方 RSS（稳定）
    data += fetch_rss("Bybit", "https://www.bybit.com/en/press/rss")

    # ✅ 可扩展其他官方源
    return data


# ========= 媒体源 =========

def fetch_media():
    data = []

    # ⚠️ 不是所有tag都有RSS，所以只用稳定源
    MEDIA_FEEDS = {
        "Cointelegraph": "https://cointelegraph.com/rss",
        "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/"
    }

    KEYWORDS = ["bybit", "okx", "bitget", "mexc", "gate"]

    for name, url in MEDIA_FEEDS.items():
        feed = feedparser.parse(url)

        for entry in feed.entries[:20]:
            dt = parse_time(entry)

            if not within_24h(dt):
                continue

            title = entry.title.lower()

            if not any(k in title for k in KEYWORDS):
                continue

            link = entry.link
            tag = tag_content(title)

            data.append(f"[Media-{name}][{tag}]\n{entry.title}\n{link}")

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

以下是数据：

{raw}

要求：

1. 只基于数据分析
2. 每个交易所提炼1个最大动态
3. 输出结构：

【竞品核心动态】
【逐家拆解】
【LBank可执行建议】

4. 媒体优先级高
5. 不允许编造
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
