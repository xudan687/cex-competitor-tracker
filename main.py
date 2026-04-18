import os
import requests
import datetime
from openai import OpenAI

# 读取环境变量
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

if not DEEPSEEK_API_KEY:
    raise ValueError("Missing DEEPSEEK_API_KEY")

if not LARK_WEBHOOK:
    raise ValueError("Missing LARK_WEBHOOK")

# 初始化 DeepSeek（必须带 /v1）
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

def generate_report():
    # 获取当前时间
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    prompt = f"""你是加密交易所市场分析师。

当前日期是：{today}（UTC时间）

请基于当前时间（2026年背景），生成一份简短竞品日报，包括：

1. 市场趋势（结合近期市场）
2. 竞品动作（模拟最近发生的真实情况）
3. 对LBank建议

要求：
- 不要使用2023或过时信息
- 内容符合当前周期（2026）
- 表达简洁，有策略性
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "生成今日竞品日报"}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content

def send_to_lark(text):
    data = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }

    resp = requests.post(LARK_WEBHOOK, json=data)
    if resp.status_code != 200:
        raise Exception(f"Lark send failed: {resp.text}")

def main():
    report = generate_report()
    print("Generated report:")
    print(report)

    send_to_lark(report)
    print("Sent to Lark successfully!")

if __name__ == "__main__":
    main()
