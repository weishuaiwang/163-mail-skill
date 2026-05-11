#!/usr/bin/env python3
"""
163 邮箱搜索脚本
支持关键词、发件人、日期范围搜索
"""
import argparse
import imaplib
import json
import os
import sys
import email
from email.header import decode_header
from email import utils as email_utils

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
    required = ["IMAP_HOST", "IMAP_PORT", "EMAIL", "PASSWORD"]
    for k in required:
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

def get_body_preview(msg):
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
    return body[:150].strip()

def search_mail(folder, query, frm, before, after, limit):
    creds = load_credentials()
    mail = IMAP4_SSL_ID(creds["IMAP_HOST"], int(creds["IMAP_PORT"]))
    mail.send_id()
    mail.login(creds["EMAIL"], creds["PASSWORD"])
    mail.select(folder)

    criteria_parts = []
    if query:
        criteria_parts.append(f'SUBJECT "{query}"')
        criteria_parts.append(f'FROM "{query}"')
        criteria_parts.append(f'BODY "{query}"')
    if frm:
        criteria_parts.append(f'FROM "{frm}"')
    if before:
        criteria_parts.append(f'BEFORE {before}')
    if after:
        criteria_parts.append(f'SINCE {after}')

    # IMAP AND logic：用空格连接
    criteria = " ".join(criteria_parts) if criteria_parts else "ALL"

    _, msgs = mail.search(None, criteria)
    msg_ids = msgs[0].split()

    results = []
    count = 0
    for mid in reversed(msg_ids):
        if count >= limit:
            break
        _, data = mail.fetch(mid, "(RFC822)")
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        msg = email.message_from_bytes(raw)

        subject = decode_str(msg.get("Subject", "(无主题)"))
        frm = format_addr(msg, "From")
        date = msg.get("Date", "")

        # 关键词高亮摘要
        body = get_body_preview(msg)

        results.append({
            "id": mid.decode(),
            "from": frm,
            "subject": subject,
            "date": date,
            "body_preview": body,
        })
        count += 1

    mail.logout()
    print(json.dumps({
        "query": query,
        "folder": folder,
        "total_matched": len(msg_ids),
        "returned": len(results),
        "emails": results
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="163 邮箱搜索")
    parser.add_argument("--query", default="", help="搜索关键词")
    parser.add_argument("--folder", default="INBOX")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--from", dest="frm", default="", help="发件人过滤")
    parser.add_argument("--before", default="", help="早于日期 (DD-Mmm-YYYY, e.g. 01-Jan-2026)")
    parser.add_argument("--after", default="", help="晚于日期 (DD-Mmm-YYYY)")
    args = parser.parse_args()
    search_mail(args.folder, args.query, args.frm, args.before, args.after, args.limit)
