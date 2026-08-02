"""
send_email.py
---------------
读取 report.json 中的 email_html_body，透过 Gmail SMTP 寄出每日报告。

需要的环境变量（皆从 GitHub Secrets 传入）：
- EMAIL_USER : 寄件者 Gmail 帐号
- EMAIL_PASS : Gmail「应用程式密码」(不是登入密码，需另外申请)
- EMAIL_TO   : 收件者信箱
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
EMAIL_TO = os.environ["EMAIL_TO"]


def main():
    with open("report.json", "r", encoding="utf-8") as f:
        report = json.load(f)

    html_body = report["email_html_body"]
    date = report["date"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"每日 GitHub 開源技能日報 - {date}"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())

    print(f"郵件已寄出至 {EMAIL_TO}")


if __name__ == "__main__":
    main()
