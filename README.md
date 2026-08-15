# AI-Skill 每週開源技能報告

這個倉庫會**每週一**自動：
1. 抓取 GitHub 上 Top 10 Star 仓库 与 Top 10 快速上升仓库
2. **排除掉上一週已經報告過的仓库**，避免連續兩週重複同一批項目
3. 呼叫 Gemini API 產生繁體中文摘要与分类
4. 把每个项目写入 `{分类}/{项目名}/README.md`
5. 產生 HTML 報告並寄送 Email

## 排程時間
每週一 台北時間 08:00（對應 UTC 週一 00:00，cron: `0 0 * * 1`）
仓库 `Actions` 分頁可以隨時手動觸發測試（`workflow_dispatch`）。

## 去重機制
`previous_repos.json`（仓库根目錄）記錄上一週選出的 20 個仓库 full_name。
每次執行前會先讀取這份清單，抓取時自動跳過已經在清單裡的仓库，
執行完後會用「這一週」的清單覆蓋掉它，供下一週比對使用。

## 分類結構
所有項目統一歸入以下四大分類（由 Gemini 判斷，固定不可自創其他分類）：
- **辦公室應用**：CRM、寫作/簡報生成、數據分析儀表板、職涯資源等非技術性商業工具
- **寫程式**：程式語言、框架、開發工具、DevOps、資安、程式教育資源
- **AI Skill**：獨立的 AI 能力/工具（推理引擎、語音/影像 AI 工具、模型本身）
- **AI Agent**：具自主性、多步驟決策能力的 AI 代理框架

## 資料夾結構
```
{分類}/{repo_name}/README.md       -> 每個項目的分類與摘要
寫程式/skills/{skill_name}/        -> 可重複使用的 Claude Skill 包（非週報自動產生，手動收錄）
reports/{date}.html                -> 每週產出的 HTML 報告存檔
previous_repos.json                -> 去重用，記錄上一週選出的仓库清單
raw_data.json                      -> 當週抓取到的原始 GitHub 資料
report.json                        -> 當週完整結構化報告資料
scripts/                           -> 執行腳本（fetch_repos.py / generate_report.py / send_email.py）
.github/workflows/                 -> 自動化排程設定
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

