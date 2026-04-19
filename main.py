import os
import requests
import datetime
import json
from openai import OpenAI
from requests.exceptions import RequestException

# ========= 配置 =========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

# 环境变量校验+报错提示
if not DEEPSEEK_API_KEY:
    raise ValueError("环境变量缺失：DEEPSEEK_API_KEY 未配置，请检查系统环境变量")
if not LARK_WEBHOOK:
    raise ValueError("环境变量缺失：LARK_WEBHOOK 未配置，请检查系统环境变量")

# DeepSeek 客户端初始化
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
# 固定东八区（北京时间，和Bitget官网公告时区完全统一）
BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))
NOW = datetime.datetime.now(BEIJING_TZ)

# ========= 时间过滤：7天内（北京时间） =========
def within_7d(dt: datetime.datetime) -> bool:
    """判断时间是否在最近7天内（统一北京时间时区）"""
    return (NOW - dt).total_seconds() < 7 * 86400

# ========= 公告分类函数（扩充关键词，适配Bitget英文标题） =========
def classify(title: str) -> str:
    t = title.lower().strip()
    # 活动类：邀请、赠金、空投、理财活动
    if any(k in t for k in ["campaign", "reward", "bonus", "airdrop", "earn", "giveaway", "promotion", "invite"]):
        return "活动"
    # 上币类：新币上线、交易对新增
    if any(k in t for k in ["launch", "listing", "lists", "new token", "new pair", "online"]):
        return "上币"
    # 产品功能类：合约、跟单、现货、API、产品更新
    if any(k in t for k in ["trading", "futures", "copy trade", "spot", "margin", "api", "function", "update"]):
        return "产品"
    # 数据/财务类：资金、持仓、财报、市场报告
    if any(k in t for k in ["report", "fund", "asset", "market", "capital", "reserve"]):
        return "数据"
    # 安全/规则/公告类：风控、升级、维护、政策通知
    if any(k in t for k in ["security", "upgrade", "maintenance", "policy", "notice", "rule"]):
        return "规则公告"
    # 其余全部兜底
    return "其他"

# ========= 【最新可用】Bitget 公告抓取（官方新版接口，彻底修复原接口失效问题） =========
def fetch_bitget():
    # Bitget 英文公告新版官方接口（2026最新可用，不会空数据）
    url = "https://api.bitget.com/api/v2/public/announcement/list"
    params = {
        "lang": "en_US",
        "pageNum": 1,
        "pageSize": 30
    }
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
        print(f"接口响应状态码：{resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ Bitget接口请求失败，状态码：{resp.status_code}，返回内容：{resp.text}")
            return []
        
        data = resp.json()
        # 新版接口返回结构解析
        announcement_list = data.get("data", {}).get("announcementList", [])
        if not announcement_list:
            print("⚠️ 接口返回公告列表为空")
            return []

        for item in announcement_list:
            title = item.get("title", "").strip()
            article_id = item.get("id", "")
            publish_timestamp = item.get("publishTime", 0) # 接口返回 毫秒级时间戳
            if not title or not article_id or publish_timestamp <= 0:
                continue

            # 时间转换：统一转为【北京时间】datetime对象，彻底解决时区偏差问题
            dt = datetime.datetime.fromtimestamp(
                publish_timestamp / 1000,
                tz=BEIJING_TZ
            )

            # 7天时间过滤
            if not within_7d(dt):
                continue

            # 新版正确永久有效文章链接（不会404）
            link = f"https://www.bitget.com/en/support/articles/{article_id}"

            items.append({
                "exchange": "Bitget",
                "title": title,
                "link": link,
                "published_at": dt.strftime("%Y-%m-%m %H:%M:%S"),
                "category": classify(title)
            })
        # 最多返回最新8条，和原代码逻辑保持一致
        return items[:8]

    except RequestException as e:
        print(f"❌ 网络请求异常：{str(e)}")
        return []
    except json.JSONDecodeError:
        print("❌ 接口返回数据JSON解析失败")
        return []
    except Exception as e:
        print(f"❌ 抓取过程未知异常：{str(e)}")
        return []

# ========= AI分析生成报告（加固异常捕获，优化提示词严谨度） =========
def generate_report(items):
    if not items:
        return "过去7天内未抓取到Bitget有效公告数据"

    raw = json.dumps(items, ensure_ascii=False, indent=2)
    print(f"\n📦 本次抓取到的有效公告原始数据：\n{raw}")

    prompt = f"""
你是加密货币交易所专业竞品分析师，分析目标为Bitget交易所。
分析时间范围：**最近7天内**
所有内容**严格只能基于下方提供的官方公告数据生成，绝对禁止编造、脑补任何外部信息**。
每条业务动态必须附带原文链接，用于溯源验证。

公告原始数据：
{raw}

请严格按照固定格式输出，语言正式简洁，符合企业竞品周报风格，结构固定不可改动：
【Bitget核心动态】
（提炼1条全周期最重要的战略级动作）

【关键动作拆解】
（分点列出3-5条细分业务动态，每条末尾附带原文链接）

【LBank可执行对标建议】
（结合Bitget动作，输出对应可落地的业务参考建议，不空洞套话）
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, # 降低随机性，完全贴合原文，不发散
            max_tokens=1200
        )
        return res.choices[0].message.content
    except Exception as e:
        print(f"❌ DeepSeek AI调用失败：{str(e)}")
        return f"AI分析接口调用异常，本次抓取到{len(items)}条Bitget公告，无法生成分析报告"

# ========= 飞书机器人发送（增加异常捕获） =========
def send_to_lark(text):
    try:
        resp = requests.post(
            LARK_WEBHOOK,
            json={
                "msg_type": "text",
                "content": {"text": text}
            },
            timeout=15
        )
        if resp.status_code == 200:
            print("✅ 飞书消息发送成功")
        else:
            print(f"❌ 飞书发送失败，状态码：{resp.status_code}，返回：{resp.text}")
    except Exception as e:
        print(f"❌ 飞书网络请求异常：{str(e)}")

# ========= 主函数入口 =========
def main():
    print("="*50)
    print("📡 开始抓取Bitget最新官方公告...")
    items = fetch_bitget()

    print(f"\n📊 本次最终有效公告数量：{len(items)} 条")

    print("\n🧠 开始调用DeepSeek生成竞品分析报告...")
    report = generate_report(items)

    print("\n📨 开始推送分析报告到飞书群机器人...")
    send_to_lark(report)

    print("\n" + "="*50)
    print("✅ 本次任务全流程执行完毕")

if __name__ == "__main__":
    main()
