import os
import requests
import datetime
from bs4 import BeautifulSoup
from openai import OpenAI

# ========== 配置 ==========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

if not DEEPSEEK_API_KEY:
    raise ValueError("Missing DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ========== 抓取函数 ==========

def fetch_mexc():
    url = "https://www.mexc.com/announcements/latest-events"
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text()[:2000]

def fetch_gate():
    url = "https://www.gate.com/zh/announcements"
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text()[:2000]

def fetch_bitget():
    url = "https://www.bitget.com/blog"
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text()[:2000]

# ========== 汇总数据 ==========

def collect_data():
    data = ""

    try:
        data += "\n[MEXC]\n" + fetch_mexc()
    except:
        data += "\n[MEXC] 抓取失败"

    try:
        data += "\n[Gate]\n" + fetch_gate()
    except:
        data += "\n[Gate] 抓取失败"

    try:
        data += "\n[Bitget]\n" + fetch_bitget()
    except:
        data += "\n[Bitget] 抓取失败"

    return data

# ========== AI分析 ==========

def generate_report(raw_data):
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d")

    prompt = f"""
你是加密交易所竞品情报分析师。

当前时间：{today}
分析范围：过去24小时（{yesterday} - {today}）

以下是抓取的真实竞品数据：

{raw_data}

请生成竞品日报：

要求：
1. 只基于提供的数据，不允许编造
2. 每家交易所提炼1个最重要动态
3. 其他用标题列出
4. 输出结构：

【竞品核心动态】
【逐家拆解】
【LBank可执行建议】

5. 如果没有有效信息，写“无重大更新”
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return response.choices[0].message.content

# ========== 飞书推送 ==========

def send_to_lark(text):
    data = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }

    requests.post(LARK_WEBHOOK, json=data)

# ========== 主函数 ==========

def main():
    print("开始抓取数据...")
    raw_data = collect_data()

    print("开始AI分析...")
    report = generate_report(raw_data)

    print("发送到飞书...")
    send_to_lark(report)

    print("完成")

if __name__ == "__main__":
    main()
