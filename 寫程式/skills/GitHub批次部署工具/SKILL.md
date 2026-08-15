---
name: github-batch-deploy
description: 用 GitHub Git Data API（blobs/trees/commits/refs）把多檔案的新增/修改/刪除/複製打包成單一 commit，取代逐檔案呼叫 Contents API（PUT/DELETE，一個檔案一個 commit，速度慢、歷史紀錄凌亂）。任何時候要透過 GitHub API 對某個 repo 做「備份輪替」「清理多個舊檔案」「一次部署多個檔案」「批次搬移/複製檔案」，或發現自己正打算對同一個 repo 連續呼叫多次 Contents API PUT/DELETE，都應該先用這個 skill 改走批次方式。單一檔案的小修改不需要，直接用 Contents API 即可。
---

# GitHub 批次部署（Git Data API）

## 為什麼要用這個

GitHub 的 Contents API（`PUT`/`DELETE /repos/{repo}/contents/{path}`）是「一個檔案一個 commit」，每次呼叫都是完整的 HTTP 請求＋Git commit，實測每次約 2-3 秒。檔案一多，總耗時等於「檔案數 × 2-3 秒」，而且會在 commit 歷史留下一堆瑣碎的單檔紀錄。

改用 **Git Data API** 後，不管要異動幾個檔案，固定只需要約 4-5 次 API 呼叫，全部包在**單一 commit** 裡完成，實測 3-8 個檔案的批次操作約 1.3-2.5 秒。

## 什麼時候該用

- 一次要新增/修改/刪除**兩個以上**的檔案
- 備份輪替（複製一批檔案到備份路徑、刪除超過保留上限的最舊備份）
- 部署多個檔案（例如前端 HTML + 版本化檔案 + Service Worker 一起推送）
- 批次搬移/重新命名檔案
- 察覺自己準備寫一個 for 迴圈逐檔案呼叫 Contents API PUT/DELETE 時，先停下來改用這個

單一檔案的小修改（改一行設定、更新一個 changelog 條目）直接用 Contents API 即可，不必為了單檔案特地走批次流程。

## 快速上手

```bash
export GH_TOKEN="ghp_..."              # GitHub Personal Access Token (repo scope)
```

⚠️ **這份 skill 講的是 Git Data API 批次操作的通用技巧，但 `scripts/gh_batch.py` 這份起始版本裡的 `REPO`／`BRANCH` 是寫死在檔案開頭的常數**（目前是 `Kevinte67228/Retro-library` / `main`），**不是讀環境變數**——用在別的 repo 前，先打開 `gh_batch.py` 把這兩個常數改掉，或是自己另外加上讀 `os.environ` 的邏輯。這是目前這份工具實際被拿去專門服務單一專案（RetroVault）之後的狀態，跟「通用」的技巧本身要分開看：技巧（Git Data API 批次 commit）是通用的，但這份起始腳本目前是為特定 repo 寫死設定值。

```python
import sys
sys.path.insert(0, "路徑/scripts")
from gh_batch import batch_commit, get_branch_head, build_path_index

# 範例1：純新增/修改
batch_commit(
    "更新設定檔與說明文件",
    adds={
        "config.json": b'{"key": "value"}',
        "README.md": open("README.md", "rb").read(),
    }
)

# 範例2：新增+刪除混在同一次commit
batch_commit(
    "重新命名檔案",
    adds={"new_name.txt": b"content"},
    deletes=["old_name.txt"]
)

# 範例3：備份輪替 — 複製既有檔案(不重新上傳內容) + 刪除過舊的備份
parent_sha, tree_sha = get_branch_head()
path_index = build_path_index(tree_sha)  # {path: blob_sha}

batch_commit(
    "備份目前版本 + 清理最舊備份",
    copies={
        "backup/v2/config.json": path_index["config.json"],  # 直接複製既有blob，不用重新download+upload
    },
    deletes=[
        "backup/v0/config.json",  # 假設v0已超過保留上限
    ],
    base_tree_sha=tree_sha,
    parent_sha=parent_sha,
)
```

## 核心函式（`scripts/gh_batch.py`）

| 函式 | 用途 |
|---|---|
| `get_branch_head()` | 回傳 `(commit_sha, tree_sha)`，目前分支（`BRANCH` 常數指定的分支）指向的最新狀態；**沒有參數可以指定分支**，要換分支得改常數 |
| `build_path_index(tree_sha)` | 回傳 `{path: blob_sha}` 完整對照表，用來複製既有檔案不必重新上傳 |
| `list_tree_recursive(tree_sha)` | 回傳所有檔案路徑清單（不含 sha） |
| `create_blob(content_bytes)` | 上傳單一檔案內容，取得 blob sha（`batch_commit` 內部會自動呼叫，通常不用手動叫） |
| `batch_commit(message, adds, deletes, copies, base_tree_sha, parent_sha)` | 核心函式，一次 commit 完成所有異動 |

⚠️ 這份起始版本**沒有**單檔案讀取的 helper 函式；要讀單一檔案內容，直接用 Contents API（`GET /repos/{repo}/contents/{path}`，見上面「跟 Contents API 的關係」段落），不需要透過 `gh_batch.py`。

## ⚠️ 已知陷阱（務必注意）

**刪除的 tree entry 不能帶 `type` 欄位**。`batch_commit` 的 `deletes` 參數已經處理好這件事，但如果你要手動組 `tree` 陣列，切記：

```python
# 正確 — 刪除項目
{"path": "some/file.txt", "mode": "100644", "sha": None}

# 錯誤 — 帶了 type 會得到 422 GitRPC::BadObjectState
{"path": "some/file.txt", "mode": "100644", "type": "blob", "sha": None}
```

新增/修改/複製的項目則**必須**帶 `"type": "blob"`：
```python
{"path": "some/file.txt", "mode": "100644", "type": "blob", "sha": blob_sha}
```

## 驗證流程有沒有做對

推送完之後，可以確認一下（`REPO` 直接照抄 `gh_batch.py` 裡寫死的常數，或自己代入實際的 repo）：
```python
import urllib.request, json, os
REPO = "Kevinte67228/Retro-library"  # 或從 gh_batch.py 的 REPO 常數取得
req = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/commits?per_page=1",
    headers={"Authorization": f"token {os.environ['GH_TOKEN']}"}
)
commit = json.loads(urllib.request.urlopen(req).read())[0]
print(commit['sha'][:10], commit['commit']['message'])
```
確認只多了**一筆** commit（而不是異動了幾個檔案就多幾筆），代表批次操作生效。

## 跟 Contents API 的關係

本質上兩者做的事情一樣，都等同於在 GitHub 網頁上編輯檔案、按「Commit changes」。差別只在 Contents API 是「每個檔案各自一次」，Git Data API 是「所有檔案打包成一次」。不需要完全捨棄 Contents API——單檔案場景它更簡單直觀，只是多檔案場景一律改用這個 skill 的批次方式。

## 跟 retrovault-deploy skill 的分工

這份 skill 只管「怎麼把多檔案異動包成一次 commit」這個技術層面，跟任何特定專案的功能開發無關。如果是在 RetroVault（Kevinte67228/Retro-library）這個專案裡工作，動手寫程式前先看 `retrovault-deploy` skill 裡的「動手前先查：全站共用機制」——那邊記錄了「先確認有沒有現成機制可以沿用，不要重複造輪子」的具體原則與案例，跟這份 skill 的定位互補但不重疊。
