import os
import requests
from openai import OpenAI

# 从 GitHub Secrets 读取
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LARK_WEBHOOK = os.getenv("LARK_WEBHOOK")

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_report():
    prompt = """
你是加密交易所市场分析师，请生成一段简短竞品日报，包括：
1. 市场趋势
2. 竞品动作
3. 对LBank建议
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
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
    requests.post(LARK_WEBHOOK, json=data)

def main():
    report = generate_report()
    send_to_lark(report)

if __name__ == "__main__":
    main()
