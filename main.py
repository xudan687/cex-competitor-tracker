import os
import re
import json
import datetime
import requests
from bs4 import BeautifulSoup
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

# 用 UTC，避免时区比较报错
NOW = datetime.datetime.now(datetime.timezone.utc)

BLOG_URL = "https://www.bitget.com/blog"


# ========= 时间 =========
def parse_ymd(text: str):
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text or "")
    if not m:
        return None
    dt = datetime.datetime.strptime(m.group(1), "%Y-%m-%d")
    return dt.replace(tzinfo=datetime.timezone.utc)


def within_7d(dt: datetime.datetime | None) -> bool:
    if not dt:
        return False
    delta = NOW - dt
    return 0 <= delta.total_seconds() <= 7 * 86400


# ========= 分类 =========
def classify(title: str) -> str:
    t = (title or "").lower()

    if any(k in t for k in ["campaign", "program", "reward", "bonus", "airdrop", "promotion"]):
        return "活动"
    if any(k in t for k in ["launches", "launch", "opens", "integrates", "upgrade", "whitepaper"]):
        return "产品"
    if any(k in t for k in ["lists", "listing"]):
        return "上币"
    if any(k in t for k in ["report", "fund", "liquidity"]):
        return "数据/品牌"
    if any(k in t for k in ["registers", "license", "compliance"]):
        return "合规"

    return "其他"


def score_item(item: dict) -> int:
    base = 1
    if item["category"] == "活动":
        base += 3
    elif item["category"] == "产品":
        base += 2
    elif item["category"] == "上币":
        base += 2
    elif item["category"] == "数据/品牌":
        base += 1
    return base


# ========= 抓取 Bitget Blog =========
def fetch_bitget_blog():
    resp = requests.get(BLOG_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # 核心思路：
    # 1. 找所有 /blog/articles/ 链接
    # 2. 在链接附近向上找日期 YYYY-MM-DD
    # 3. 只保留过去7天
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/blog/articles/" not in href:
            continue

        title = a.get_text(" ", strip=True)
        if len(title) < 12:
            continue

        # 真实链接：如果已经是完整链接就直接用，否则补域名
        if href.startswith("http"):
            link = href
        else:
            link = "https://www.bitget.com" + href

        # 在当前链接附近找日期。Bitget blog 页面日期通常就在卡片附近。
        nearby_texts = []

        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            nearby_texts.append(parent.get_text(" ", strip=True))
            parent = parent.parent

        merged_text = " ".join(nearby_texts)
        published_dt = parse_ymd(merged_text)

        # 如果附近没找到日期，就放弃，不猜
        if not published_dt:
            continue

        if not within_7d(published_dt):
            continue

        # 尝试抓一小段摘要，方便 AI 不脑补
        snippet = ""
        try:
            card_text = a.parent.get_text(" ", strip=True)
            snippet = card_text[:300]
        except Exception:
            pass

        item = {
            "exchange": "Bitget",
            "title": title,
            "link": link,
            "published_at": published_dt.strftime("%Y-%m-%d"),
            "category": classify(title),
            "snippet": snippet
        }
        results.append(item)

    # 去重：按 link 去重
    uniq = {}
    for x in results:
        uniq[x["link"]] = x

    items = list(uniq.values())
    items.sort(key=lambda x: (x["published_at"], score_item(x)), reverse=True)

    return items[:8]


# ========= AI 总结 =========
def generate_report(items: list[dict]) -> str:
    raw = json.dumps(items, ensure_ascii=False, indent=2)

    prompt = f"""
你是加密交易所竞品分析师。

当前时间（UTC）：{NOW.strftime("%Y-%m-%d")}
分析范围：过去7天
对象：仅 Bitget
数据源：仅 Bitget 官方 Blog

以下是已经过滤好的真实数据（含标题、日期、链接、摘要）：
{raw}

严格要求：
1. 只能基于这些数据分析，不允许编造。
2. 只能讨论 Bitget，不允许出现 Binance、OKX、Bybit 等其他交易所。
3. 每一条“核心动态”或“关键动作拆解”都必须附上对应原始链接。
4. 如果信息不足，就明确写“过去7天内未发现足够多的官方更新”，不要脑补。
5. 不要扩展未提供的文章细节，只能基于 title / snippet 能确认的内容。
6. 输出要像人工周报，简洁、可信、可核验。

输出结构：
【Bitget核心动态】
【关键动作拆解】
【LBank可执行建议】
"""

    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    return res.choices[0].message.content


# ========= 飞书 =========
def send_to_lark(text: str):
    payload = {
        "msg_type": "text",
        "content": {"text": text}
    }
    resp = requests.post(LARK_WEBHOOK, json=payload, timeout=20)
    resp.raise_for_status()


# ========= 主程序 =========
def main():
    print("Fetching Bitget blog...")
    items = fetch_bitget_blog()

    print("Items found:", len(items))
    print(json.dumps(items, ensure_ascii=False, indent=2))

    if not items:
        report = "【Bitget核心动态】\n过去7天内未抓取到足够的 Bitget 官方 Blog 更新，请检查页面结构或放宽时间范围。"
    else:
        print("Generating report...")
        report = generate_report(items)

    print("Sending to Lark...")
    send_to_lark(report)
    print("Done.")


if __name__ == "__main__":
    main()
