"""
generate_report.py
--------------------
读取 raw_data.json：
- 呼叫 Gemini API，只請它做「分類」與「繁體中文摘要」這兩件需要語意理解的事
- 其餘欄位（Star數、語言、連結、儲存路徑）與 HTML 報告排版，
  一律由 Python 程式碼自己組出來，確保每天欄位 100% 一致，不受 AI 當天發揮影響

輸出：
1. report.json      完整結構化結果
2. 每個分類文件夾下的 README.md
3. reports/{date}.html
"""

import os
import json
import re
import html
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Kevinte67228/AI-Skill")

MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


CATEGORIES = ["辦公室應用", "寫程式", "AI Skill", "AI Agent"]
CATEGORY_DEFINITIONS = """
- 辦公室應用：非技術性的商業/生產力工具，例如 CRM、寫作或簡報生成工具、數據分析儀表板、職涯資源等
- 寫程式：程式語言、框架、開發工具、DevOps、資安、程式教育資源等軟體工程相關項目
- AI Skill：獨立的 AI 能力或工具（非自主代理），例如推理引擎、語音/影像 AI 工具、模型本身
- AI Agent：具自主性、多步驟決策能力的 AI 代理框架與代理工具
"""


def build_prompt(raw_data: dict) -> str:
    all_items = raw_data["top_star"] + raw_data["fast_rising"]
    minimal = [
        {"full_name": item["full_name"], "description": item["description"], "language": item["language"]}
        for item in all_items
    ]
    categories_list = "、".join(CATEGORIES)
    return f"""你是一位開源科技分析師。以下是 {len(minimal)} 個 GitHub 專案的基本資訊。

{json.dumps(minimal, ensure_ascii=False, indent=2)}

請針對每一個專案（用 full_name 對應）完成：
1. category_name：從以下「這四個固定分類」中選一個最貼切的，不可自創其他分類名稱：
{CATEGORY_DEFINITIONS}
   分類名稱必須完全是這四個字串之一：{categories_list}
2. summary：一段繁體中文摘要，包含核心功能、使用場景、為什麼值得關注，控制在 2-3 句話

請嚴格只回傳一個 JSON 物件，不要有 markdown code block 包裹，不要有前言。結構如下：

{{
  "items": [
    {{"full_name": "string", "category_name": "string", "summary": "string"}}
  ]
}}
"""


def call_gemini(prompt: str) -> dict:
    resp = requests.post(
        f"{API_URL}?key={GEMINI_API_KEY}",
        headers={"content-type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "maxOutputTokens": 65536,
            },
        },
        timeout=300,
    )
    if not resp.ok:
        print("=== Gemini API 呼叫失敗 ===")
        print("status_code:", resp.status_code)
        print("response body:", resp.text[:3000])
        resp.raise_for_status()

    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        print("=== Gemini 沒有回傳任何 candidate ===")
        print(json.dumps(data, ensure_ascii=False)[:3000])
        raise RuntimeError("Gemini API 未回傳內容，可能被安全機制擋下")

    finish_reason = candidates[0].get("finishReason")
    if finish_reason == "MAX_TOKENS":
        print("警告: 回應被 maxOutputTokens 截斷，內容可能不完整，請考慮提高 maxOutputTokens")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)

    cleaned = re.sub(r"^```json\s*|```\s*$", "", text.strip())

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("=== JSON 解析失敗，印出原始回應方便除錯 ===")
        print("錯誤:", e)
        print("原始回應前 2000 字:")
        print(cleaned[:2000])
        print("原始回應後 2000 字:")
        print(cleaned[-2000:])
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise


def build_full_report(raw_data: dict, ai_result: dict) -> dict:
    """把 AI 給的 category/summary 跟原始資料(stars/language/url等)合併，
    並由程式碼自己算出 local_path 與 repo_dir_url，確保每個欄位都一定存在。"""
    ai_by_name = {item["full_name"]: item for item in ai_result.get("items", [])}

    all_items = [(item, "Top Star") for item in raw_data["top_star"]] + \
                [(item, "Fast-Rising") for item in raw_data["fast_rising"]]

    categories_map = {}
    for item, item_type in all_items:
        full_name = item["full_name"]
        ai_info = ai_by_name.get(full_name, {})
        category_name = ai_info.get("category_name", "")
        if category_name not in CATEGORIES:
            print(f"警告: {full_name} 的分類「{category_name}」不在固定四類中，改為預設「寫程式」")
            category_name = "寫程式"
        summary = ai_info.get("summary", "（本次未取得摘要）")

        local_path = f"{category_name}/{item['name']}/README.md"
        repo_dir_url = f"https://github.com/{GITHUB_REPOSITORY}/tree/main/{category_name}/{item['name']}"

        full_item = {
            "name": item["name"],
            "type": item_type,
            "original_url": item["html_url"],
            "stars": item["stars"],
            "language": item["language"],
            "local_path": local_path,
            "repo_dir_url": repo_dir_url,
            "summary": summary,
        }
        categories_map.setdefault(category_name, []).append(full_item)

    categories = [
        {"category_name": name, "items": categories_map[name]}
        for name in CATEGORIES
        if name in categories_map
    ]
    return {"date": raw_data["date"], "categories": categories}


def write_readmes(report: dict):
    for category in report["categories"]:
        for item in category["items"]:
            path = item["local_path"]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {item['name']}\n\n")
                f.write(f"**類型**: {item['type']}\n\n")
                f.write(f"**語言**: {item['language']} | **Star**: {item['stars']:,}\n\n")
                f.write(f"**原始連結**: {item['original_url']}\n\n")
                f.write(f"**收錄日期**: {report['date']}\n\n")
                f.write("## 摘要\n\n")
                f.write(item["summary"] + "\n")


def render_email_html(report: dict) -> str:
    """完全由 Python 組出 HTML，欄位固定不變，不受 AI 發揮影響。"""
    badge_color = {"Top Star": "#22c55e", "Fast-Rising": "#3b82f6"}
    parts = [f"""
    <div style="font-family: -apple-system, 'PingFang TC', 'Microsoft JhengHei', sans-serif; max-width: 680px; margin: 0 auto; color: #1f2937;">
      <h1 style="color: #007bff; text-align:center; font-size: 24px;">GitHub 開源科技報告</h1>
      <p style="text-align:center; color:#666; margin-bottom: 30px;">日期: {report['date']}</p>
    """]

    for category in report["categories"]:
        parts.append(f"""
      <h2 style="border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; margin-top: 32px;">{html.escape(category['category_name'])}</h2>
        """)
        for item in category["items"]:
            color = badge_color.get(item["type"], "#6b7280")
            parts.append(f"""
      <div style="background:#f9fafb; border-radius:8px; padding:16px; margin-bottom:14px; border:1px solid #e5e7eb;">
        <p style="margin:0 0 6px 0;">
          <strong style="color:#007bff; font-size:1.1em;">{html.escape(item['name'])}</strong>
          <span style="background:{color}; color:#fff; font-size:0.75em; padding:2px 8px; border-radius:10px; margin-left:8px;">{item['type']}</span>
        </p>
        <p style="margin:0 0 8px 0; color:#666; font-size:0.9em;">語言: {html.escape(item['language'])} | Star: {item['stars']:,}</p>
        <p style="margin:0 0 10px 0; font-size:0.95em; line-height:1.6;">{html.escape(item['summary'])}</p>
        <p style="margin:0; font-size:0.9em;">
          <a href="{item['original_url']}" style="color:#007bff; text-decoration:none;">原始連結</a>
          &nbsp;|&nbsp;
          <a href="{item['repo_dir_url']}" style="color:#007bff; text-decoration:none;">本地倉庫路徑</a>
        </p>
      </div>
            """)

    parts.append("</div>")
    return "".join(parts)


def write_html_report(report: dict) -> str:
    os.makedirs("reports", exist_ok=True)
    path = f"reports/{report['date']}.html"
    html_body = render_email_html(report)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_body)
    return path, html_body


def main():
    with open("raw_data.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    prompt = build_prompt(raw_data)
    ai_result = call_gemini(prompt)

    report = build_full_report(raw_data, ai_result)
    html_path, html_body = write_html_report(report)
    report["email_html_body"] = html_body

    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    write_readmes(report)

    print(f"報告產生完成: report.json, 各分類 README.md, {html_path}")


if __name__ == "__main__":
    main()
