"""
GitHub Git Data API 批次操作工具
用單一 commit 完成多檔案的新增/修改/刪除,取代逐檔案呼叫 Contents API。
"""
import urllib.request, json, base64, time, os

TOKEN = os.environ.get("GH_TOKEN", "")  # 由使用者每次對話提供，不寫死在檔案內；也可用 export GH_TOKEN=ghp_... 設定
REPO = "Kevinte67228/AI-Skill"
API = f"https://api.github.com/repos/{REPO}"
BRANCH = "main"

def _req(method, path, body=None, ok_statuses=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"token {TOKEN}",
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if ok_statuses and e.code in ok_statuses:
            return None
        raise

def _retry(fn, *a, tries=5, **kw):
    for i in range(tries):
        try:
            return fn(*a, **kw)
        except Exception as e:
            print("retry:", e)
            time.sleep(3)
    raise RuntimeError("failed after retries: " + str(a))

def get_branch_head():
    """回傳 (commit_sha, tree_sha)；若倉庫是全新空的(沒有任何commit/branch)，回傳 (None, None)"""
    ref = _req("GET", f"/git/ref/heads/{BRANCH}", ok_statuses=[404, 409])
    if ref is None:
        return None, None
    commit_sha = ref["object"]["sha"]
    commit = _retry(_req, "GET", f"/git/commits/{commit_sha}")
    tree_sha = commit["tree"]["sha"]
    return commit_sha, tree_sha

def list_tree_recursive(tree_sha):
    """回傳整個 repo 底下所有檔案路徑清單(該tree往下遞迴)"""
    t = _retry(_req, "GET", f"/git/trees/{tree_sha}?recursive=1")
    return [item["path"] for item in t["tree"] if item["type"] == "blob"]

def build_path_index(tree_sha):
    """回傳 {path: blob_sha} 完整對照表，供「複製既有檔案到新路徑」使用，
    不需要重新下載+上傳內容，只要在新 tree 裡引用同一個 blob sha 即可。"""
    t = _retry(_req, "GET", f"/git/trees/{tree_sha}?recursive=1")
    return {item["path"]: item["sha"] for item in t["tree"] if item["type"] == "blob"}

def create_blob(content_bytes):
    b64 = base64.b64encode(content_bytes).decode()
    result = _retry(_req, "POST", "/git/blobs", {"content": b64, "encoding": "base64"})
    return result["sha"]

def batch_commit(message, adds=None, deletes=None, copies=None, base_tree_sha=None, parent_sha=None):
    """
    一次 commit 完成多檔案新增/修改/刪除/複製。
    adds: {path: content_bytes, ...}       (新增或覆蓋，需要上傳新內容)
    deletes: [path, path, ...]             (刪除)
    copies: {new_path: existing_blob_sha}  (複製既有檔案到新路徑，不用重新上傳內容，速度更快；
                                             existing_blob_sha 從 build_path_index() 取得)
    回傳新的 commit sha。
    """
    adds = adds or {}
    deletes = deletes or []
    copies = copies or {}
    is_empty_repo = False
    if base_tree_sha is None or parent_sha is None:
        parent_sha, base_tree_sha = get_branch_head()
        if parent_sha is None:
            is_empty_repo = True  # 全新空倉庫，還沒有任何 commit/branch

    tree_entries = []
    for path, content in adds.items():
        blob_sha = create_blob(content)
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob_sha})
    for path, existing_sha in copies.items():
        tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": existing_sha})
    for path in deletes:
        tree_entries.append({"path": path, "mode": "100644", "sha": None})

    tree_body = {"tree": tree_entries}
    if not is_empty_repo:
        tree_body["base_tree"] = base_tree_sha
    new_tree = _retry(_req, "POST", "/git/trees", tree_body)

    commit_body = {"message": message, "tree": new_tree["sha"]}
    if not is_empty_repo:
        commit_body["parents"] = [parent_sha]
    new_commit = _retry(_req, "POST", "/git/commits", commit_body)

    if is_empty_repo:
        # 空倉庫還沒有 refs/heads/main，要用 POST 建立新 ref，而不是 PATCH 既有的
        _retry(_req, "POST", "/git/refs", {
            "ref": f"refs/heads/{BRANCH}", "sha": new_commit["sha"]
        })
    else:
        _retry(_req, "PATCH", f"/git/refs/heads/{BRANCH}", {"sha": new_commit["sha"], "force": False})
    return new_commit["sha"]
