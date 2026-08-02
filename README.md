# AI-Skill 每日開源技能日報

這個倉庫會每天自動：
1. 抓取 GitHub 上 Top 10 Star 仓库 与 Top 10 快速上升仓库
2. 呼叫 Claude API 產生繁體中文摘要与分类
3. 把每个项目写入 `{分类}/{项目名}/README.md`
4. 產生 HTML 報告並寄送 Email

## 資料夾結構
```
ai-agents/          -> AI代理相关项目
web-development/     -> 网页开发相关项目
devops/               -> 部署/维运相关项目
...（依 Claude 每日自動判斷分類）
reports/              -> 每日產出的 HTML 報告存檔
scripts/              -> 執行腳本
.github/workflows/    -> 自動化排程設定
```

## 需要设定的 GitHub Secrets
| Secret 名称 | 说明 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 金鑰 |
| `EMAIL_USER` | 寄件者 Gmail 帐号 |
| `EMAIL_PASS` | Gmail 应用程式密码 |
| `EMAIL_TO` | 收件者信箱 |

`GITHUB_TOKEN` 由 GitHub Actions 自動提供，不需自行設定。
