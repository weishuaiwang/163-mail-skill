# 163 Mail Skill

> 使用 Python imaplib 接入 163 邮箱（IMAP/SMTP），支持读取、发送、搜索邮件。新邮件监控 + 飞书推送开箱即用。
>
> **核心亮点**：解决了 163 邮箱 IMAP "Unsafe Login" 拦截问题——通过发送 IMAP ID 命令（RFC 2971）标识客户端身份。

## 功能

| 功能 | 说明 |
|------|------|
| 📥 读取邮件 | IMAP 读取收件箱，支持分页 |
| ✉️ 发送邮件 | SMTP SSL 发送，支持附件 |
| 🔍 搜索邮件 | 关键词 / 发件人 / 日期过滤 |
| 📊 邮件摘要 | 按发件人分组汇总 |
| 🔔 新邮件监控 | 配合 cron job 每 N 分钟推送新邮件到飞书 |

## 环境要求

- Python 3.8+
- 163 邮箱账号（开启 IMAP/SMTP 服务）
- 网络可访问 `imap.163.com:993` 和 `smtp.163.com:465`

## 快速开始

### 1. 克隆仓库

```bash
git clone git@github.com:weishuaiwang/163-mail-skill.git
cd 163-mail-skill
```

### 2. 配置授权码

编辑 `references/credentials.md`，填入你的 163 邮箱信息：

```bash
# 163 邮箱凭证配置
IMAP_HOST=imap.163.com
IMAP_PORT=993
SMTP_HOST=smtp.163.com
SMTP_PORT=465
EMAIL=your_email@163.com
PASSWORD=your授权码       # 不是登录密码，是客户端授权码
SENDER_NAME=小虾米        # 发件人显示名
```

**授权码获取**：163 邮箱网页 → 设置 → POP3/SMTP/IMAP → 开启 IMAP/SMTP → 授权码管理

### 3. 安装依赖

```bash
# 仅使用标准库，无需额外安装
python3 --version  # 确认 Python 3.8+
```

### 4. 测试连接

```bash
# 读取收件箱
python3 scripts/mail_client.py --action read --folder INBOX --limit 5

# 发送测试邮件
python3 scripts/mail_client.py --action send \
  --to your_email@163.com \
  --subject "测试" \
  --body "Hello from 163 Mail Skill"

# 检查新邮件
python3 scripts/mail_client.py --action check_new --folder INBOX
```

## 脚本说明

### mail_client.py — 核心客户端

```bash
# 读取邮件
python3 scripts/mail_client.py --action read --folder INBOX --limit 10 --offset 0

# 发送邮件
python3 scripts/mail_client.py --action send \
  --to recipient@example.com \
  --subject "主题" \
  --body "正文" \
  --cc "cc@example.com" \
  --attachments "/path/to/file.pdf"

# 检查新邮件（自动记录检查点）
python3 scripts/mail_client.py --action check_new --folder INBOX
```

### mail_search.py — 邮件搜索

```bash
python3 scripts/mail_search.py --query "关键词" --folder INBOX --limit 20
python3 scripts/mail_search.py --from "noreply@" --folder INBOX --limit 10
python3 scripts/mail_search.py --after "01-May-2026" --before "31-May-2026"
```

### mail_summary.py — 邮件摘要

```bash
# 总结最近 7 天的邮件
python3 scripts/mail_summary.py --folder INBOX --days 7 --limit 20
```

## 接入飞书新邮件推送

使用 cron job 每 5 分钟检查一次，有新邮件推送到飞书：

```bash
# 配合飞书 messaging skill 推送，示例 prompt：
# "检查 163 邮箱新邮件，有新邮件时将主题、发件人、时间和正文摘要通过飞书发送给用户"
```

## ⚠️ 163 邮箱特殊说明

163 邮箱在 IMAP 连接时有**客户端身份验证**要求。如果遇到：

```
SELECT Unsafe Login. Please contact kefu@188.com for help
```

**这是 163 的安全策略拦截，不是密码错误。** 解决方案是发送 IMAP ID 命令（RFC 2971）：

```python
class IMAP4_SSL_ID(imaplib.IMAP4_SSL):
    def send_id(self):
        tag = self._new_tag()
        cmd = tag + b' ID ("name" "your-client" "version" "1.0.0" ' \
              b'"vendor" "your-org" "support-email" "you@example.com" ' \
              b'"os" "linux" "os-version" "1.0")' + imaplib.CRLF
        self.send(cmd)
        # 读取响应...
```

本项目所有脚本已内置此修复。

## 项目结构

```
163-mail-skill/
├── README.md
├── LICENSE
├── SKILL.md                      # Hermes Agent 技能定义
├── references/
│   └── credentials.md            # 凭证配置（不提交到 git）
└── scripts/
    ├── mail_client.py           # 读取/发送/检查新邮件
    ├── mail_search.py            # 搜索邮件
    └── mail_summary.py           # 邮件摘要
```

## License

MIT License
