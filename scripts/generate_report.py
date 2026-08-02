"""
generate_report.py
--------------------
读取 raw_data.json，呼叫 Claude API 产出：
- 每个仓库的繁体中文摘要
- 技术分类
- 本地存放路径 + 仓库内直连链接
- 一份漂亮的 HTML 邮件报告

输出：
1. report.json      完整结构化结果
2. 每个分类文件夹下的 README.md
3. index_report.html 用于寄信 / 也会写一份到仓库根目录 reports/{date}.html
"""

import os
import json
import re
import requests

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Kevinte67228/AI-Skill")

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"


def build_prompt(raw_data: dict) -> str:
    return f"""你是一位開源科技分析師。以下是今天(來源日期: {raw_data['date']})抓取到的 GitHub 資料，
包含 Top 10 Star 仓库 (top_star) 和 Top 10 快速上升仓库 (fast_rising)。

原始資料:
{json.dumps(raw_data, ensure_ascii=False, indent=2)}

請完成以下任務：

1. 為這 20 個項目各寫一段繁體中文摘要，包含：核心功能、使用場景、為什麼值得關注。控制在 2-3 句話。
2. 為每個項目自動分類到合適的技術類別（例如：ai-agents, web-development, devops, utilities, data-science, machine-learning 等，可自行判斷最貼切的類別，類別名稱一律使用小寫連字號英文，如 ai-agents）。
3. 為每個項目定義本地儲存路徑：{{category_name}}/{{project_name}}/README.md
4. 產生倉庫內的直連連結：https://github.com/{GITHUB_REPOSITORY}/tree/main/{{category_name}}/{{project_name}}
5. 產生一份美觀、乾淨、適合直接當 Email HTML 內文的完整報告，裡面每個項目都要有可點擊的連結（連到 original_url 和 repo_dir_url）。HTML 需使用 inline style（因為多數郵件客戶端不支援外部 CSS），並依照分類分組呈現。

請嚴格只回傳一個 JSON 物件，不要有任何 markdown code block 包裹符號（不要用```json```），不要有任何前言或說明文字。JSON 結構如下：

{{
  "date": "YYYY-MM-DD",
  "categories": [
    {{
      "category_name": "string",
      "items": [
        {{
          "name": "string",
          "type": "Top Star" 或 "Fast-Rising",
          "original_url": "string",
          "local_path": "string",
          "repo_dir_url": "string",
          "summary": "string"
        }}
      ]
    }}
  ],
  "email_html_body": "string"
}}
"""


def call_claude(prompt: str) -> dict:
    resp = requests.post(
        API_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )
    # 保险起见，去掉可能出现的 ```json 包裹
    cleaned = re.sub(r"^```json\s*|```\s*$", "", text.strip())
    return json.loads(cleaned)


def write_readmes(report: dict):
    for category in report.get("categories", []):
        for item in category.get("items", []):
            path = item["local_path"]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {item['name']}\n\n")
                f.write(f"**類型**: {item['type']}\n\n")
                f.write(f"**原始連結**: {item['original_url']}\n\n")
                f.write(f"**收錄日期**: {report['date']}\n\n")
                f.write("## 摘要\n\n")
                f.write(item["summary"] + "\n")


def write_html_report(report: dict):
    os.makedirs("reports", exist_ok=True)
    path = f"reports/{report['date']}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(report["email_html_body"])
    return path


def main():
    with open("raw_data.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    prompt = build_prompt(raw_data)
    report = call_claude(prompt)

    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    write_readmes(report)
    html_path = write_html_report(report)

    print(f"報告產生完成: report.json, 各分類 README.md, {html_path}")


if __name__ == "__main__":
    main()
