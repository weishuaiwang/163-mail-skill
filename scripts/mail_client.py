#!/usr/bin/env python3
"""
163 邮箱 IMAP/SMTP 客户端
支持：读取邮件、发送邮件、检查新邮件
"""
import argparse
import imaplib
import smtplib
import json
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.header import Header
from email import utils as email_utils
from email.header import decode_header
import base64
from datetime import datetime

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "../references/credentials.md")
LAST_CHECK_PATH = os.path.join(os.path.dirname(__file__), ".last_check.json")

def load_credentials():
    creds = {}
    if os.path.exists(CREDENTIALS_PATH):
        with open(CREDENTIALS_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    creds[key.strip()] = val.strip()
    required = ["IMAP_HOST", "IMAP_PORT", "SMTP_HOST", "SMTP_PORT", "EMAIL", "PASSWORD"]
    for k in required:
        if k not in creds:
            print(f"ERROR: Missing credential '{k}' in references/credentials.md", file=sys.stderr)
            sys.exit(1)
    return creds

def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)

def format_addr(msg, key):
    val = msg.get(key, "")
    decoded = decode_str(val)
    name, addr = email_utils.parseaddr(decoded)
    return f"{name} <{addr}>" if name else addr

def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in disp:
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
                break
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    return body[:200].strip()

class IMAP4_SSL_ID(imaplib.IMAP4_SSL):
    """扩展 IMAP4_SSL，支持 IMAP ID 命令（RFC 2971）"""

    def send_id(self):
        """手动发送 IMAP ID 命令，绕过 imaplib 内置 Commands 权限检查"""
        tag = self._new_tag()
        cmd = tag + b' ID ("name" "openclaw-agent" "version" "1.0.0" ' \
              b'"vendor" "openclaw-mail-skill" "support-email" "support@openclaw.ai" ' \
              b'"os" "linux" "os-version" "1.0")' + imaplib.CRLF
        self.send(cmd)
        while True:
            resp = self.readline()
            if not resp:
                break
            if resp.startswith(tag):
                return resp

def imap_connect(creds):
    mail = IMAP4_SSL_ID(creds["IMAP_HOST"], int(creds["IMAP_PORT"]))
    # 发送 IMAP ID 信息（RFC 2971），避免 163 服务器 Unsafe Login 拦截
    mail.send_id()
    mail.login(creds["EMAIL"], creds["PASSWORD"])
    return mail


def smtp_connect(creds):
    smtp = smtplib.SMTP_SSL(creds["SMTP_HOST"], int(creds["SMTP_PORT"]))
    smtp.login(creds["EMAIL"], creds["PASSWORD"])
    return smtp

def action_read(folder, limit, offset):
    creds = load_credentials()
    mail = imap_connect(creds)
    mail.select(folder)

    # 按时间倒序搜索
    _, msgs = mail.search(None, "ALL")
    msg_ids = msgs[0].split()
    total = len(msg_ids)

    start = max(0, total - offset - limit)
    end = total - offset
    page_ids = msg_ids[start:end]

    results = []
    for mid in reversed(page_ids):
        _, data = mail.fetch(mid, "(RFC822)")
        import email
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        msg = email.message_from_bytes(raw)

        date = msg.get("Date", "")
        results.append({
            "id": mid.decode(),
            "from": format_addr(msg, "From"),
            "to": format_addr(msg, "To"),
            "subject": decode_str(msg.get("Subject", "(无主题)")),
            "date": date,
            "body_preview": get_body(msg),
        })

    mail.logout()
    print(json.dumps({"total": total, "folder": folder, "emails": results}, ensure_ascii=False, indent=2))

def action_send(to, subject, body, cc, attachments):
    creds = load_credentials()
    msg = MIMEMultipart()
    sender_name = creds.get("SENDER_NAME", "")
    msg["From"] = email_utils.formataddr((sender_name, creds["EMAIL"]))
    msg["To"] = to
    msg["Subject"] = Header(subject, "utf-8")
    if cc:
        msg["Cc"] = cc
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachments:
        for path in attachments.split(","):
            path = path.strip()
            if not path:
                continue
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            import email.encoders
            email.encoders.encode_base64(part)
            filename = os.path.basename(path)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

    recipients = [to]
    if cc:
        recipients += [x.strip() for x in cc.split(",")]

    smtp = smtp_connect(creds)
    smtp.sendmail(creds["EMAIL"], recipients, msg.as_string())
    smtp.quit()
    print(json.dumps({"status": "sent", "to": to, "subject": subject}))

def action_check_new(folder):
    creds = load_credentials()
    last_check = None
    if os.path.exists(LAST_CHECK_PATH):
        try:
            with open(LAST_CHECK_PATH) as f:
                last_check = json.load(f).get(folder)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    mail = imap_connect(creds)
    mail.select(folder)
    _, msgs = mail.search(None, "ALL")
    all_ids = msgs[0].split()
    total = len(all_ids)
    mail.logout()

    new_count = 0
    if last_check:
        unseen = [mid for mid in all_ids if int(mid) > int(last_check)]
        new_count = len(unseen)
    else:
        new_count = total

    # 更新记录
    if all_ids:
        latest_id = max(int(m) for m in all_ids)
        state = {}
        if os.path.exists(LAST_CHECK_PATH):
            with open(LAST_CHECK_PATH) as f:
                state = json.load(f)
        state[folder] = latest_id
        with open(LAST_CHECK_PATH, "w") as f:
            json.dump(state, f)

    print(json.dumps({
        "folder": folder,
        "total": total,
        "new_since_last_check": new_count,
        "last_checked": datetime.now().isoformat()
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="163 邮箱客户端")
    parser.add_argument("--action", required=True, choices=["read", "send", "check_new"])
    parser.add_argument("--folder", default="INBOX")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--to", help="收件人")
    parser.add_argument("--subject", help="主题")
    parser.add_argument("--body", help="正文")
    parser.add_argument("--cc", help="抄送，逗号分隔")
    parser.add_argument("--attachments", help="附件路径，逗号分隔")
    args = parser.parse_args()

    if args.action == "read":
        action_read(args.folder, args.limit, args.offset)
    elif args.action == "send":
        if not args.to or not args.subject or not args.body:
            print("ERROR: --to, --subject, --body are required for send", file=sys.stderr)
            sys.exit(1)
        action_send(args.to, args.subject, args.body, args.cc, args.attachments)
    elif args.action == "check_new":
        action_check_new(args.folder)
