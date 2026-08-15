# AI-Skill 每週開源技能報告

📋 **[點此查看快速索引清單 INDEX.md](INDEX.md)** —— 所有已收錄專案依分類列出，含版本號與快速連結

這個倉庫會**每週日**自動：
1. 台北時間 **06:00**：抓取 GitHub 上 Top 10 Star 仓库 与 Top 10 快速上升仓库，呼叫 Gemini API 產生繁體中文摘要与分类，寫回仓库
2. 台北時間 **08:00**：讀取剛產生好的報告，寄送 Email（獨立排程，不受產生報告耗時影響）

## 排程時間
- 產生報告：每週日 台北時間 06:00（UTC 週六 22:00，cron: `0 22 * * 6`）
- 寄送 Email：每週日 台北時間 08:00（UTC 週日 00:00，cron: `0 0 * * 0`）
- 仓库 `Actions` 分頁可以隨時手動觸發測試（`workflow_dispatch`）

## 去重與版本更新機制
`previous_repos.json`（仓库根目錄）是一份**累積式登記簿**，記錄歷來所有收錄過的仓库，
每筆記錄比對的是 GitHub 的 `pushed_at`（實際程式碼推送時間）：
- **全新項目** → 正常收錄
- **真的重複**（沒有新的 commit）→ 排除，不出現在報告
- **版本更新**（上次收錄後又有新推送）→ **不排除**，正常收錄，並在 README／Email 上標註 🆕 版本更新
  - 儲存路徑固定，只會覆蓋成最新內容，不會累積多個版本
  - 若這次分類跟上次不同，會自動清掉舊分類下的舊檔案

## 分類結構
所有項目統一歸入以下四大分類（由 Gemini 判斷，固定不可自創其他分類）：
- **辦公室應用**：CRM、寫作/簡報生成、數據分析儀表板、職涯資源等非技術性商業工具
- **寫程式**：程式語言、框架、開發工具、DevOps、資安、程式教育資源
- **AI Skill**：獨立的 AI 能力/工具（推理引擎、語音/影像 AI 工具、模型本身）
- **AI Agent**：具自主性、多步驟決策能力的 AI 代理框架

## 資料夾結構
```
INDEX.md                           -> 所有已收錄專案的快速索引清單（含版本號、連結）
{分類}/{repo_name}/README.md       -> 每個項目的分類、摘要、版本號、作者最後更新日期
寫程式/skills/{skill_name}/        -> 可重複使用的 Claude Skill 包（非週報自動產生，手動收錄）
reports/{date}.html                -> 每週產出的 HTML 報告存檔
previous_repos.json                -> 去重與版本更新用的累積式登記簿
raw_data.json                      -> 當週抓取到的原始 GitHub 資料
report.json                        -> 當週完整結構化報告資料
scripts/                           -> 執行腳本（fetch_repos.py / generate_report.py / send_email.py）
.github/workflows/                 -> 自動化排程設定（daily-report.yml=產生報告, weekly-send-email.yml=寄信）
```

## 需要设定的 GitHub Secrets
| Secret 名称 | 说明 |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API 金鑰（用於產生摘要與分類，需連結有效billing帐号） |
| `EMAIL_USER` | 寄件者 Gmail 帐号 |
| `EMAIL_PASS` | Gmail 应用程式密码（非登入密碼） |
| `EMAIL_TO` | 收件者信箱 |

`GITHUB_TOKEN` 由 GitHub Actions 自動提供，不需自行設定。

## 手動編輯注意事項
`.github/workflows/` 底下的檔案因為 GitHub API 權限限制，
無法透過一般 Token 自動部署，異動需要在 GitHub 網頁上手動編輯 commit。

