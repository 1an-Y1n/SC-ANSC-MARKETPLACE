---
name: email-notify
description: Send emails (plain text or styled HTML) with optional CC and attachments via SMTP — no external dependencies, pure Python stdlib
---

# Email Notify Skill

Send plain-text emails (with optional CC and file attachments) using SMTP. Zero external dependencies — uses Python standard library only. Suitable for AI-triggered notifications, report delivery, troubleshooting completion alerts, and weekly digest sends.

## Use Cases

- Notify assignee when AI troubleshooting analysis is complete
- Send weekly story-point report (with report.md as body-file)
- Deliver Jira audit results to a reviewer
- Alert on CI/CD failure with log attachment

## Prerequisites

- Python 3.6+
- SMTP server accessible from your machine (no TLS/auth required for internal servers)
- Email config file (see Configuration below)

## Configuration

**Credential recommendation:** Store config at `~/.agents/config/email-notify.json` (user-level, never committed). The skill also reads the legacy path `~/.config/windsurf/email_config.json`, and a local fallback at `<skill>/config/email_config.json`.

```bash
mkdir -p ~/.agents/config
cp skills/email-notify/config/email_config.json.example ~/.agents/config/email-notify.json
# Edit with your SMTP details
```

`email_config.json` fields:

| Field | Description | Example |
|-------|-------------|---------|
| `smtp_host` | SMTP server hostname | `smtp.your-company.com` |
| `smtp_port` | SMTP port (default 25) | `25` |
| `from_addr` | Sender email address | `ai-cowork@your-company.com` |
| `sender_name` | Display name in From header | `AI Cowork Kit` |

**Environment variable overrides** (highest priority):

| Variable | Maps to |
|----------|---------|
| `EMAIL_SMTP_HOST` | `smtp_host` |
| `EMAIL_SMTP_PORT` | `smtp_port` |
| `EMAIL_FROM_ADDR` | `from_addr` |
| `EMAIL_SENDER_NAME` | `sender_name` |

## Usage

### Send a simple email

```bash
python skills/email-notify/scripts/send_email.py send \
    --to recipient@example.com \
    --subject "Analysis Complete" \
    --body "The AI troubleshooting analysis is done. See attached report."
```

### Send with CC

```bash
python skills/email-notify/scripts/send_email.py send \
    --to owner@example.com \
    --cc manager@example.com,team@example.com \
    --subject "Weekly Report" \
    --body "Please find this week's story points below."
```

### Send with body from file (e.g. a Markdown report)

```bash
python skills/email-notify/scripts/send_email.py send \
    --to team@example.com \
    --subject "Task Audit Report" \
    --body-file /tmp/audit_report.md
```

### Send with attachments

```bash
python skills/email-notify/scripts/send_email.py send \
    --to reviewer@example.com \
    --subject "RCA Document" \
    --body "Please review the attached RCA." \
    --attach /tmp/rca.pdf \
    --attach /tmp/log.txt
```

### Send as styled HTML (with plain-text fallback)

Pass an HTML body (`--html-body` or `--html-body-file`) alongside a plain-text body.
The mail is then sent as `multipart/alternative`, so clients that cannot render HTML
fall back to the text part.

```bash
python skills/email-notify/scripts/send_email.py send \
    --to team@example.com \
    --subject "Weekly digest" \
    --body "Plain-text fallback for non-HTML clients" \
    --html-body-file /tmp/digest.html \
    --attach report.md
```

### Use from Python (programmatic)

```python
from skills.email_notify.scripts.send_email import send_mail

send_mail(
    subject="Troubleshooting Done",
    body="Phase 0-5 complete. Root cause identified.",
    to_emails=["owner@example.com"],
    cc_emails=["manager@example.com"],
    attachments=["/tmp/rca_report.md"],
)
```

## How the AI should use this skill

### Step 1: Check configuration before sending

Before running any email command, check whether the config exists (preferred path, or the legacy fallback):

```bash
if [ -f ~/.agents/config/email-notify.json ] || [ -f ~/.config/windsurf/email_config.json ]; then
  echo "configured"
else
  echo "not configured"
fi
```

**If not configured**, do NOT attempt to send. Instead, guide the user:

> "Email config not found. Please set it up first:
> ```bash
> mkdir -p ~/.agents/config
> cp skills/email-notify/config/email_config.json.example ~/.agents/config/email-notify.json
> ```
> Then edit `~/.agents/config/email-notify.json` with your SMTP settings:
> - `smtp_host`: your SMTP server (e.g. `smtp.your-company.com`)
> - `from_addr`: the sender email address
>
> Or set environment variables instead:
> ```bash
> export EMAIL_SMTP_HOST=smtp.your-company.com
> export EMAIL_FROM_ADDR=ai-cowork@your-company.com
> ```"

### Step 2: Send the email

Once configured, run the send command and report the result to the user.

**Success output:** `[✓] Email sent to recipient@example.com: Subject Line`

**Failure output:** `[✗] Send failed: <error detail>` — report the error detail to the user.

## Integration with Other Skills

### With ai-troubleshooting-workflow

After Phase 5 (documentation), add a send step:

```bash
python skills/email-notify/scripts/send_email.py send \
    --to $ISSUE_OWNER \
    --subject "[AI RCA] $JIRA_ID complete" \
    --body-file /tmp/rca_summary.md
```

### With meeting-analysis

After generating the meeting report:

```bash
python skills/email-notify/scripts/send_email.py send \
    --to participants@example.com \
    --subject "Meeting Summary: $MEETING_TITLE" \
    --body-file /tmp/meeting_report.md
```

## Reusability

★★★★★ — Works for any team with SMTP access. Only `email_config.json` needs adjustment per deployment.
