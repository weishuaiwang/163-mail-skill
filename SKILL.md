---
name: mail-163
description: 163 邮箱（IMAP/SMTP）收发技能 — 读取、发送、搜索、摘要，IMAP ID 命令解决 Unsafe Login 问题。适用于「查看邮件」「发送邮件」「搜索邮件」「邮件摘要」「新邮件提醒」。
tags: [Email, 163, IMAP, SMTP, Netease]
version: 1.0.0
author: weishuaiwang
license: MIT
---

# mail-163 — 163 邮箱技能

## 配置

编辑 `references/credentials.md`：

```bash
IMAP_HOST=imap.163.com
IMAP_PORT=993
SMTP_HOST=smtp.163.com
SMTP_PORT=465
EMAIL=your_email@163.com
PASSWORD=your授权码
SENDER_NAME=你的名字
```

## 快速使用

```bash
# 读取邮件
python3 scripts/mail_client.py --action read --folder INBOX --limit 10

# 发送邮件
python3 scripts/mail_client.py --action send \
  --to recipient@example.com --subject "Hello" --body "正文"

# 搜索邮件
python3 scripts/mail_search.py --query "关键词" --folder INBOX

# 邮件摘要
python3 scripts/mail_summary.py --folder INBOX --days 7

# 检查新邮件
python3 scripts/mail_client.py --action check_new --folder INBOX
```

## 163 邮箱 Unsafe Login 解决方案

163 邮箱 IMAP 连接时要求发送 IMAP ID 命令（RFC 2971）标识客户端身份，否则 SELECT INBOX 被拦截。本技能内置 `IMAP4_SSL_ID` 类自动处理：

```python
class IMAP4_SSL_ID(imaplib.IMAP4_SSL):
    def send_id(self):
        tag = self._new_tag()
        cmd = tag + b' ID ("name" "openclaw-agent" "version" "1.0.0" ' \
              b'"vendor" "openclaw-mail-skill" "support-email" "you@example.com" ' \
              b'"os" "linux" "os-version" "1.0")' + imaplib.CRLF
        self.send(cmd)
        while True:
            resp = self.readline()
            if resp.startswith(tag):
                return resp
```
