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

        version_info = item.get("version") or {}

        full_item = {
            "name": item["name"],
            "full_name": full_name,
            "type": item_type,
            "original_url": item["html_url"],
            "stars": item["stars"],
            "language": item["language"],
            "local_path": local_path,
            "repo_dir_url": repo_dir_url,
            "summary": summary,
            "pushed_at": item.get("pushed_at"),
            "is_update": item.get("is_update", False),
            "previous_local_path": item.get("previous_local_path"),
            "version_tag": version_info.get("tag"),
            "version_published_at": version_info.get("published_at"),
        }
        categories_map.setdefault(category_name, []).append(full_item)

    categories = [
        {"category_name": name, "items": categories_map[name]}
        for name in CATEGORIES
        if name in categories_map
    ]
    return {"date": raw_data["date"], "categories": categories}


def cleanup_stale_files(report: dict):
    """版本更新的項目，如果這次被分到跟上次不同的分類，
    要先刪掉舊分類底下的舊 README.md，確保同一個仓库只留一份最新的。"""
    for category in report["categories"]:
        for item in category["items"]:
            if not item["is_update"]:
                continue
            old_path = item["previous_local_path"]
            if not old_path or old_path == item["local_path"]:
                continue
            if os.path.exists(old_path):
                os.remove(old_path)
                print(f"已清除舊分類檔案: {old_path}（版本更新，新分類為 {item['local_path']}）")
                parent = os.path.dirname(old_path)
                try:
                    if parent and not os.listdir(parent):
                        os.rmdir(parent)
                except OSError:
                    pass


def update_registry(report: dict):
    """把這次報告收錄的仓库寫回歷史登記簿（累積式更新，
    不會清掉其他沒出現在這次報告的舊記錄，確保之後幾週都還能正確比對）。"""
    registry_file = "previous_repos.json"
    registry = {}
    if os.path.exists(registry_file):
        with open(registry_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        registry = data.get("repos", {})

    for category in report["categories"]:
        for item in category["items"]:
            registry[item["full_name"]] = {
                "pushed_at": item["pushed_at"],
                "local_path": item["local_path"],
                "name": item["name"],
                "category": category["category_name"],
                "original_url": item["original_url"],
                "version_tag": item.get("version_tag"),
                "author_updated": format_date(item.get("version_published_at")) or format_date(item.get("pushed_at")),
            }

    with open(registry_file, "w", encoding="utf-8") as f:
        json.dump({"date": report["date"], "repos": registry}, f, ensure_ascii=False, indent=2)

    print(f"登記簿已更新，目前共累積 {len(registry)} 個仓库記錄")


def format_date(iso_str):
    """把 ISO 8601 時間字串轉成 YYYY-MM-DD，格式不對就原樣回傳。"""
    if not iso_str:
        return None
    try:
        return iso_str[:10]
    except Exception:
        return iso_str


def generate_index(report: dict):
    """從登記簿（累積了歷來所有收錄過的仓库）產生一份 INDEX.md，
    放在倉庫根目錄，依分類分組列出所有項目的快速連結，方便直接點進去。

    分類/專案名一律優先從 local_path 反推（而不是依賴額外欄位），
    因為 local_path 是每筆記錄一定會有的資訊，不會因為欄位改版而缺漏。"""
    registry_file = "previous_repos.json"
    with open(registry_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    registry = data.get("repos", {})

    by_category = {}
    for full_name, info in registry.items():
        local_path = info.get("local_path") or ""
        parts = local_path.split("/")
        category = parts[0] if len(parts) >= 3 else (info.get("category") or "未分類")
        name = parts[1] if len(parts) >= 3 else (info.get("name") or full_name)
        by_category.setdefault(category, []).append((name, info, full_name, local_path))

    lines = ["# 📋 專案快速索引\n", f"共收錄 {len(registry)} 個專案，最後更新於 {report['date']}\n"]
    ordered_categories = [c for c in CATEGORIES if c in by_category] + \
                          [c for c in by_category if c not in CATEGORIES]

    for category in ordered_categories:
        items = sorted(by_category[category], key=lambda x: x[0].lower())
        lines.append(f"\n## {category}（{len(items)}）\n")
        lines.append("| 專案 | 版本 | 作者最後更新 | 快速連結 |")
        lines.append("|---|---|---|---|")
        for name, info, full_name, local_path in items:
            folder = os.path.dirname(local_path) if local_path else f"{category}/{name}"
            folder_url = folder.replace(" ", "%20")  # Markdown連結路徑含空白需編碼，否則GitHub不會解析成超連結
            version_tag = info.get("version_tag") or "-"
            author_updated = info.get("author_updated") or "-"
            lines.append(f"| {name} | {version_tag} | {author_updated} | [{folder}]({folder_url}) |")

    with open("INDEX.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"INDEX.md 已更新，共 {len(registry)} 筆快速索引")


def write_readmes(report: dict):
    for category in report["categories"]:
        for item in category["items"]:
            path = item["local_path"]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            author_updated = format_date(item.get("version_published_at")) or format_date(item.get("pushed_at"))
            version_tag = item.get("version_tag") or "（作者未提供版本標籤）"
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {item['name']}\n\n")
                if item["is_update"]:
                    f.write("> 🆕 **版本更新**：偵測到自上次收錄後有新的程式碼推送\n\n")
                f.write(f"**類型**: {item['type']}\n\n")
                f.write(f"**語言**: {item['language']} | **Star**: {item['stars']:,}\n\n")
                f.write(f"**版本號**: {version_tag}\n\n")
                f.write(f"**作者最後更新日期**: {author_updated}\n\n")
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
            update_badge = ""
            if item["is_update"]:
                update_badge = '<span style="background:#f97316; color:#fff; font-size:0.75em; padding:2px 8px; border-radius:10px; margin-left:6px;">🆕 版本更新</span>'
            parts.append(f"""
      <div style="background:#f9fafb; border-radius:8px; padding:16px; margin-bottom:14px; border:1px solid #e5e7eb;">
        <p style="margin:0 0 6px 0;">
          <strong style="color:#007bff; font-size:1.1em;">{html.escape(item['name'])}</strong>
          <span style="background:{color}; color:#fff; font-size:0.75em; padding:2px 8px; border-radius:10px; margin-left:8px;">{item['type']}</span>
          {update_badge}
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

    cleanup_stale_files(report)

    html_path, html_body = write_html_report(report)
    report["email_html_body"] = html_body

    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    write_readmes(report)
    update_registry(report)
    generate_index(report)

    print(f"報告產生完成: report.json, 各分類 README.md, {html_path}")


if __name__ == "__main__":
    main()
