---
name: Imap Email
slug: imap-email
description: IMAP 邮件读取和处理技能，支持多账户邮件监控、规则过滤、内容提取和自动回复工作流。
category: superpowers
source: clawhub
---

# IMAP Email

IMAP email processing skill. Use to **read, filter, and process emails** from any IMAP-compatible mailbox (Gmail, Outlook, custom servers).

## When to Use

- Monitor inbox for specific emails and trigger actions
- Extract data from incoming emails (invoices, orders, reports)
- Build email-to-task automation
- Auto-categorize or respond to emails

## Connection Setup

```python
import imaplib
import email
from email.header import decode_header

# Connect to Gmail
mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
mail.login("user@gmail.com", "app_password")  # Use app-specific password

# Connect to Outlook
mail = imaplib.IMAP4_SSL("outlook.office365.com", 993)
mail.login("user@outlook.com", "password")
```

## Core Operations

### Fetch Unread Emails
```python
mail.select("inbox")
_, message_ids = mail.search(None, "UNSEEN")

for mid in message_ids[0].split():
    _, msg_data = mail.fetch(mid, "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])

    subject = decode_header(msg["Subject"])[0][0]
    sender = msg["From"]

    # Get text body
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode()
    else:
        body = msg.get_payload(decode=True).decode()
```

### Filter by Sender/Subject
```python
# Search by sender
_, ids = mail.search(None, 'FROM "invoices@supplier.com"')

# Search by subject
_, ids = mail.search(None, 'SUBJECT "Order Confirmation"')

# Since date
_, ids = mail.search(None, 'SINCE "01-Apr-2025"')

# Combined
_, ids = mail.search(None, '(FROM "alerts@github.com" UNSEEN)')
```

## Automation Patterns

```python
# Email → Todoist task
def process_flagged_emails():
    for email in get_starred_emails():
        subject = extract_subject(email)
        create_todoist_task(subject, due="tomorrow")
        mark_processed(email)
```
