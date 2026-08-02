"""
fetch_repos.py
----------------
抓取 GitHub 上：
1. Top 10 Star 数最高的仓库（近期活跃）
2. Top 10 "快速上升" 仓库（用「最近7天内建立、star数排序」作为近似指标，
   因为 GitHub 官方 API 并不直接提供 star 增速数据）

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


def search_repos(query: str, sort: str = "stars", per_page: int = 10):
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


def main():
    today = datetime.date.today()
    seven_days_ago = today - datetime.timedelta(days=7)

    # 1. Top 10 Star（整体最高星数，且近期仍有更新，避免抓到完全没维护的老项目）
    top_star_query = "stars:>1000 pushed:>" + str(today - datetime.timedelta(days=30))
    top_star_raw = search_repos(top_star_query, sort="stars", per_page=10)
    top_star = [simplify(r) for r in top_star_raw]

    # 2. Top 10 Fast-Rising（近7天内建立、star数最高 = 近似"快速窜起"的新项目）
    fast_rising_query = f"created:>{seven_days_ago} stars:>20"
    fast_rising_raw = search_repos(fast_rising_query, sort="stars", per_page=10)
    fast_rising = [simplify(r) for r in fast_rising_raw]

    output = {
        "date": str(today),
        "top_star": top_star,
        "fast_rising": fast_rising,
    }

    with open("raw_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已抓取 {len(top_star)} 个 Top Star 仓库, {len(fast_rising)} 个 Fast-Rising 仓库")


if __name__ == "__main__":
    main()
