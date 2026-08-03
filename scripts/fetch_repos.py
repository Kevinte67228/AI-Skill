"""
fetch_repos.py
----------------
抓取 GitHub 上（每週執行一次）：
1. Top 10 Star 数最高的仓库（近期活跃）
2. Top 10 "快速上升" 仓库（用「最近7天内建立、star数排序」作为近似指标，
   因为 GitHub 官方 API 并不直接提供 star 增速数据）

會讀取 previous_repos.json（上一週選出的 20 個 full_name），
從這次搜尋結果中排除掉，避免連續兩週報告重複同一批仓库。
抓取完成後會把「這一週選出的 20 個 full_name」寫回 previous_repos.json，
供下一週執行時排除用。

输出：一份 JSON 档 raw_data.json，供下一步 (generate_report.py) 使用。
"""

import os
import json
import datetime
import requests

GITHUB_TOKEN = os.environ.get("GH_TOKEN")  # 可选，但强烈建议提供，避免 API 速率限制
HEADERS = {
    "Accept": "application/vnd.github+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

SEARCH_URL = "https://api.github.com/search/repositories"
PREVIOUS_REPOS_FILE = "previous_repos.json"


def search_repos(query: str, sort: str = "stars", per_page: int = 30):
    params = {
        "q": query,
        "sort": sort,
        "order": "desc",
        "per_page": per_page,
    }
    resp = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("items", [])


def simplify(item: dict) -> dict:
    return {
        "name": item["name"],
        "full_name": item["full_name"],
        "html_url": item["html_url"],
        "description": item.get("description") or "",
        "stars": item["stargazers_count"],
        "language": item.get("language") or "Unknown",
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def load_previous_full_names() -> set:
    if not os.path.exists(PREVIOUS_REPOS_FILE):
        return set()
    with open(PREVIOUS_REPOS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("full_names", []))


def pick_top_n_excluding(raw_items: list, exclude: set, n: int = 10) -> list:
    """依序取前 n 個，跳過在 exclude 集合裡的項目（即上週已出現過的仓库）。"""
    picked = []
    for item in raw_items:
        simplified = simplify(item)
        if simplified["full_name"] in exclude:
            continue
        picked.append(simplified)
        if len(picked) >= n:
            break
    return picked


def main():
    today = datetime.date.today()
    seven_days_ago = today - datetime.timedelta(days=7)

    previous_full_names = load_previous_full_names()
    print(f"上週報告過 {len(previous_full_names)} 個仓库，本次將排除這些重複項目")

    # 1. Top 10 Star（整体最高星数，且近期仍有更新，避免抓到完全没维护的老项目）
    # 多抓一些候選（per_page=30），再排除掉上週出現過的，確保還能湊到 10 個
    top_star_query = "stars:>1000 pushed:>" + str(today - datetime.timedelta(days=30))
    top_star_raw = search_repos(top_star_query, sort="stars", per_page=30)
    top_star = pick_top_n_excluding(top_star_raw, previous_full_names, n=10)

    # 2. Top 10 Fast-Rising（近7天内建立、star数最高 = 近似"快速窜起"的新项目）
    fast_rising_query = f"created:>{seven_days_ago} stars:>20"
    fast_rising_raw = search_repos(fast_rising_query, sort="stars", per_page=30)
    fast_rising = pick_top_n_excluding(fast_rising_raw, previous_full_names, n=10)

    if len(top_star) < 10:
        print(f"警告: 排除重複後 Top Star 只湊到 {len(top_star)} 個（候選池可能不夠大）")
    if len(fast_rising) < 10:
        print(f"警告: 排除重複後 Fast-Rising 只湊到 {len(fast_rising)} 個（候選池可能不夠大）")

    output = {
        "date": str(today),
        "top_star": top_star,
        "fast_rising": fast_rising,
    }

    with open("raw_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 把這一週選出的 full_name 寫回去，供下週排除用（覆蓋，不累積，因為只需要跟「上一週」比對）
    this_week_full_names = [item["full_name"] for item in top_star + fast_rising]
    with open(PREVIOUS_REPOS_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": str(today), "full_names": this_week_full_names}, f, ensure_ascii=False, indent=2)

    print(f"已抓取 {len(top_star)} 个 Top Star 仓库, {len(fast_rising)} 个 Fast-Rising 仓库")


if __name__ == "__main__":
    main()
