import os
import requests
from openai import OpenAI

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    raise ValueError("Missing DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

def generate_report():
    prompt = """你是加密交易所市场分析师，请生成一段简短竞品日报，包括：
1. 市场趋势
2. 竞品动作
3. 对LBank建议
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "请生成一份测试竞品报告"}
        ]
    )

    return response.choices[0].message.content

def send_to_lark(text):
    data = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }
    requests.post(os.getenv("LARK_WEBHOOK"), json=data)

def main():
    report = generate_report()
    send_to_lark(report)

if __name__ == "__main__":
    main()
