#!/usr/bin/env python3
"""
163 邮箱摘要生成脚本
总结最近 N 天内的邮件，按发件人/主题分组
"""
import argparse
import imaplib
import json
import os
import sys
import email
from datetime import datetime, timedelta
from email.header import decode_header
from email import utils as email_utils
from collections import defaultdict

CREDENTIALS_PATH=os.path.join(os.path.dirname(__file__), "../references/credentials.md")

class IMAP4_SSL_ID(imaplib.IMAP4_SSL):
    """扩展 IMAP4_SSL，支持 IMAP ID 命令（RFC 2971），绕过 163 Unsafe Login 拦截"""
    def send_id(self):
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

def load_credentials():
    creds = {}
    if os.path.exists(CREDENTIALS_PATH):
        with open(CREDENTIALS_PATH) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    creds[key.strip()] = val.strip()
    for k in ["IMAP_HOST", "IMAP_PORT", "EMAIL", "PASSWORD"]:
        if k not in creds:
            print(f"ERROR: Missing credential '{k}'", file=sys.stderr)
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
    return body.strip()

def generate_summary(folder, limit, days):
    creds = load_credentials()
    mail = IMAP4_SSL_ID(creds["IMAP_HOST"], int(creds["IMAP_PORT"]))
    mail.send_id()
    mail.login(creds["EMAIL"], creds["PASSWORD"])
    mail.select(folder)

    # 计算日期范围
    since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    _, msgs = mail.search(None, f"SINCE {since_date}")
    msg_ids = msgs[0].split()

    emails = []
    for mid in reversed(msg_ids[-limit*2:]):  # 最多取2倍，分组用
        _, data = mail.fetch(mid, "(RFC822)")
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        msg = email.message_from_bytes(raw)

        subject = decode_str(msg.get("Subject", "(无主题)"))
        frm = format_addr(msg, "From")
        date = msg.get("Date", "")
        body = get_body(msg)

        emails.append({
            "id": mid.decode(),
            "from": frm,
            "subject": subject,
            "date": date,
            "body": body[:500],
        })

    mail.logout()

    # 按发件人分组
    by_sender = defaultdict(list)
    for e in emails:
        addr = e["from"].split("<")[-1].rstrip(">") if "<" in e["from"] else e["from"]
        by_sender[addr].append(e)

    summary = {
        "period_days": days,
        "folder": folder,
        "total_emails": len(emails),
        "unique_senders": len(by_sender),
        "senders": []
    }

    for addr, msgs in sorted(by_sender.items(), key=lambda x: -len(x[1])):
        sender_info = {
            "email": addr,
            "count": len(msgs),
            "subjects": list(set(m["subject"] for m in msgs[:5])),
            "latest_date": max(m["date"] for m in msgs),
            "preview": msgs[0]["body"][:200].strip() if msgs else "",
        }
        summary["senders"].append(sender_info)

    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="163 邮箱摘要")
    parser.add_argument("--folder", default="INBOX")
    parser.add_argument("--limit", type=int, default=20, help="最多汇总的邮件数")
    parser.add_argument("--days", type=int, default=7, help="汇总 N 天内的邮件")
    args = parser.parse_args()
    generate_summary(args.folder, args.limit, args.days)
