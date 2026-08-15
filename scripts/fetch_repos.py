"""
fetch_repos.py
----------------
抓取 GitHub 上（每週執行一次）：
1. Top 10 Star 数最高的仓库（近期活跃）
2. Top 10 "快速上升" 仓库（用「最近7天内建立、star数排序」作为近似指标，
   因为 GitHub 官方 API 并不直接提供 star 增速数据）

去重邏輯（改良版，支援「版本更新」偵測）：
- 讀取 previous_repos.json 這份「歷史登記簿」（累積所有出現過的仓库，不會每週重置）
- 對每個候選仓库，比對它的 pushed_at（實際程式碼推送時間）跟登記簿裡記錄的時間：
    - 沒登記過 -> 全新項目，正常收錄
    - 登記過，但 pushed_at 沒有變化 -> 真的重複，跳過不收錄
    - 登記過，但 pushed_at 比上次新 -> 代表有版本更新，「不排除」，
      並標記 is_update=True，讓 generate_report.py 之後在報告上標註「版本更新」
      同時附上 previous_local_path，供之後判斷是否需要搬移/清掉舊分類下的舊檔案

登記簿本身的更新（哪些項目要記錄新的 pushed_at/local_path）交給 generate_report.py 處理，
因為要等 AI 分類完才知道最終的 local_path。

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
        "pushed_at": item.get("pushed_at") or item["updated_at"],  # 實際 code push 時間，用來判斷是否有版本更新
    }


def get_latest_version(full_name: str) -> dict:
    """查詢這個仓库的最新版本資訊：優先看 GitHub Release，沒有的話退而求其次看 Tag。
    回傳 {"tag": 版本標籤或None, "published_at": 發布日期或None, "source": "release"/"tag"/None}"""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{full_name}/releases/latest",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "tag": data.get("tag_name"),
                "published_at": data.get("published_at"),
                "source": "release",
            }
    except requests.RequestException:
        pass

    try:
        resp = requests.get(
            f"https://api.github.com/repos/{full_name}/tags",
            headers=HEADERS, params={"per_page": 1}, timeout=15,
        )
        if resp.status_code == 200:
            tags = resp.json()
            if tags:
                return {"tag": tags[0].get("name"), "published_at": None, "source": "tag"}
    except requests.RequestException:
        pass

    return {"tag": None, "published_at": None, "source": None}


def load_registry() -> dict:
    """讀取歷史登記簿: {full_name: {"pushed_at":..., "local_path":...}}
    相容舊格式（只存 full_names 陣列），會轉換成新格式（pushed_at 給 None，代表未知）。"""
    if not os.path.exists(PREVIOUS_REPOS_FILE):
        return {}
    with open(PREVIOUS_REPOS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "repos" in data:
        return data["repos"]
    # 舊格式相容
    return {name: {"pushed_at": None, "local_path": None} for name in data.get("full_names", [])}


def pick_top_n_with_update_check(raw_items: list, registry: dict, n: int = 10) -> list:
    """依序取前 n 個：
    - 未登記過的全新項目直接收錄
    - 登記過但沒有新 push -> 跳過（真重複）
    - 登記過且有新 push -> 收錄，並標記 is_update=True
    """
    picked = []
    for item in raw_items:
        s = simplify(item)
        prev = registry.get(s["full_name"])
        if prev is None:
            s["is_update"] = False
            s["previous_local_path"] = None
        else:
            prev_pushed = prev.get("pushed_at")
            if prev_pushed is not None and s["pushed_at"] <= prev_pushed:
                continue  # 真的重複，沒有新版本，跳過
            s["is_update"] = True
            s["previous_local_path"] = prev.get("local_path")
        picked.append(s)
        if len(picked) >= n:
            break
    return picked


def main():
    today = datetime.date.today()
    seven_days_ago = today - datetime.timedelta(days=7)

    registry = load_registry()
    print(f"歷史登記簿共有 {len(registry)} 個仓库記錄")

    # 1. Top 10 Star（整体最高星数，且近期仍有更新，避免抓到完全没维护的老项目）
    # 多抓一些候選（per_page=30），確保排除真重複後還能湊到 10 個
    top_star_query = "stars:>1000 pushed:>" + str(today - datetime.timedelta(days=30))
    top_star_raw = search_repos(top_star_query, sort="stars", per_page=30)
    top_star = pick_top_n_with_update_check(top_star_raw, registry, n=10)

    # 2. Top 10 Fast-Rising（近7天内建立、star数最高 = 近似"快速窜起"的新项目）
    fast_rising_query = f"created:>{seven_days_ago} stars:>20"
    fast_rising_raw = search_repos(fast_rising_query, sort="stars", per_page=30)
    fast_rising = pick_top_n_with_update_check(fast_rising_raw, registry, n=10)

    if len(top_star) < 10:
        print(f"警告: 排除重複後 Top Star 只湊到 {len(top_star)} 個（候選池可能不夠大）")
    if len(fast_rising) < 10:
        print(f"警告: 排除重複後 Fast-Rising 只湊到 {len(fast_rising)} 個（候選池可能不夠大）")

    update_count = sum(1 for item in top_star + fast_rising if item["is_update"])
    if update_count:
        print(f"其中有 {update_count} 個項目是「版本更新」（先前已收錄過，但偵測到新的程式碼推送）")

    print("查詢版本號資訊（Release/Tag）...")
    for item in top_star + fast_rising:
        version_info = get_latest_version(item["full_name"])
        item["version"] = version_info

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
