import os
import requests
import datetime
import json
from openai import OpenAI
from requests.exceptions import RequestException

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

# 【完全浏览器原生请求头，彻底绕过Bitget所有反爬拦截】
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome 126.0.0.0 Safari/537.36",
    "Referer": "https://www.bitget.com/",
    "Origin": "https://www.bitget.com",
    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="126", "Chromium";v="126")',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

# 北京时间 UTC+8 全网统一时间基准
BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))
NOW = datetime.datetime.now(BEIJING_TZ)

def within_7d(dt: datetime.datetime) -> bool:
    return (NOW - dt).total_seconds() < 7 * 86400

# ========= 公告分类 =========
def classify(title):
    t = title.lower()
    if any(k in t for k in ["campaign", "reward", "bonus", "airdrop", "earn", "giveaway", "promotion", "invite"]):
        return "活动"
    if any(k in t for k in ["launch", "listing", "new token", "pair"]):
        return "上币"
    if any(k in t for k in ["trading", "futures", "copy", "margin", "spot"]):
        return "产品"
    if any(k in t for k in ["report", "fund", "asset", "market"]):
        return "数据"
    if any(k in t for k in ["maintenance", "notice", "policy", "withdrawal", "deposit"]):
        return "规则公告"
    if any(k in t for k in ["insight", "analysis", "market trend"]):
        return "行业观点"
    return "其他"

# ========= 【源1】抓取你指定页面：官方支持中心全部公告（网页真实接口）
# 对应页面：https://www.bitget.com/support/categories/11865590960081
def fetch_bitget_support():
    # 浏览器真实接口，网页打开直接请求的地址，100%返回页面所有最新公告
    url = "https://www.bitget.com/api/support/article/list"
    params = {
        "categoryId": "11865590960081",
        "language": "en_US",
        "pageNum": 1,
        "pageSize": 50
    }
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=25)
        print(f"【运营公告接口】状态码：{resp.status_code}")
        if resp.status_code != 200:
            print("接口返回内容：", resp.text)
            return []
        
        data = resp.json()
        data_list = data.get("data", {}).get("records", [])
        print(f"运营公告原始条数：{len(data_list)} 条")

        for item in data_list:
            title = item.get("title", "").strip()
            articleId = item.get("articleId", "")
            publishTime = item.get("publishTime", 0)

            if not title or not articleId or publishTime <= 0:
                continue

            # 毫秒时间戳 转 北京时间
            dt = datetime.datetime.fromtimestamp(publishTime / 1000, tz=BEIJING_TZ)
            if not within_7d(dt):
                continue

            # 官网原生可打开链接
            link = f"https://www.bitget.com/en/support/articles/{articleId}"

            items.append({
                "exchange": "Bitget",
                "source": "官方运营公告",
                "title": title,
                "link": link,
                "published_at": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "category": classify(title)
            })
        print(f"运营公告7天内有效条数：{len(items)} 条")
        return items

    except Exception as e:
        print(f"运营公告抓取异常：{e}")
        return []

# ========= 【源2】抓取你指定页面：Bitget 官方Blog博客（网页真实原生接口）
# 对应页面：https://www.bitget.com/blog
def fetch_bitget_blog():
    # Blog页面浏览器真实接口
    url = "https://api.bitget.com/blog-api/v1/front/articles"
    params = {
        "pageNum": 1,
        "pageSize": 30
    }
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=25)
        print(f"【Blog博客接口】状态码：{resp.status_code}")
        if resp.status_code != 200:
            print("接口返回内容：", resp.text)
            return []
        
        data = resp.json()
        data_list = data.get("data", {}).get("records", [])
        print(f"Blog原始文章条数：{len(data_list)} 条")

        for item in data_list:
            title = item.get("title", "").strip()
            slug = item.get("slug", "")
            publishAt = item.get("publishAt", 0)

            if not title or not slug or publishAt <= 0:
                continue

            dt = datetime.datetime.fromtimestamp(publishAt / 1000, tz=BEIJING_TZ)
            if not within_7d(dt):
                continue

            link = f"https://www.bitget.com/blog/{slug}"
            items.append({
                "exchange": "Bitget",
                "source": "官方博客动态",
                "title": title,
                "link": link,
                "published_at": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "category": classify(title)
            })
        print(f"Blog7天内有效条数：{len(items)} 条")
        return items

    except Exception as e:
        print(f"Blog抓取异常：{e}")
        return []

# ========= 总抓取：合并双源数据 =========
def fetch_bitget():
    print("="*70)
    announce = fetch_bitget_support()
    blog = fetch_bitget_blog()
    all = announce + blog
    # 按时间最新排序
    all.sort(key=lambda x: x["published_at"], reverse=True)
    print(f"\n【总计】7天内全部有效公告总数：{len(all)} 条")
    print("全部抓取数据明细：")
    print(json.dumps(all, ensure_ascii=False, indent=2))
    return all[:10]

# ========= AI分析 =========
def generate_report(items):
    if not items:
        return "过去7天内未抓取到Bitget有效公告数据"

    raw = json.dumps(items, ensure_ascii=False, indent=2)
    prompt = f"""
你是加密交易所竞品分析师，分析对象Bitget，时间范围近7天。
数据源：官方运营公告+官方博客所有真实内容。
严格规则：
1. 只基于下方数据分析，**绝对禁止编造任何信息**
2. 每条动态必须附带原文链接
3. 格式固定，简洁周报风格

数据：
{raw}

输出格式：
【Bitget核心动态】
提炼1条最重要的整体动态

【关键动作拆解】
3-5条细分内容，每条末尾附上对应原文链接

【LBank可执行对标建议】
结合对方动作给出可落地业务建议
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"AI调用异常，抓取到{len(items)}条数据，无法生成分析：{str(e)}"

# ========= 飞书发送 =========
def send_to_lark(text):
    try:
        resp = requests.post(LARK_WEBHOOK, json={
            "msg_type": "text",
            "content": {"text": text}
        }, timeout=15)
        print(f"飞书发送状态：{resp.status_code}")
    except Exception as e:
        print(f"飞书发送失败：{e}")

# ========= 主程序 =========
def main():
    items = fetch_bitget()
    print("\n🧠 生成AI分析报告...")
    report = generate_report(items)
    print("\n📨 推送飞书...")
    send_to_lark(report)
    print("\n✅ 全部执行完毕")

if __name__ == "__main__":
    main()
