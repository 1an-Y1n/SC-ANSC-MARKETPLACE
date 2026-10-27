#!/usr/bin/env python3
# Copyright (c) 2026 SerComm Corporation. All Rights Reserved.
#
# SerComm Corporation reserves the right to make changes to this document
# without notice. SerComm Corporation makes no warranty, representation or
# guarantee regarding the suitability of its products for any particular
# purpose.
#
# SerComm Corporation assumes no liability arising out of the application or
# use of any product or circuit.
#
# SerComm Corporation specifically disclaims any and all liability, including
# without limitation consequential or incidental damages; neither does it convey
# any license under its patent rights, nor the rights of others.

"""
Email sending utility for AI Cowork Kit.

Configuration precedence (high to low):
1. Environment variables (EMAIL_SMTP_HOST, EMAIL_FROM_ADDR, etc.)
2. User-level config: ~/.agents/config/email-notify.json
3. Legacy user-level config: ~/.config/windsurf/email_config.json
4. Local config: <skill>/config/email_config.json

Usage:
    python send_email.py send --to user@example.com --subject "Hello" --body "World"
    python send_email.py send --to a@ex.com --cc b@ex.com --subject "Report" --body-file report.md
    python send_email.py send --to a@ex.com --subject "With Attachment" --attach report.pdf
    python send_email.py send --to a@ex.com --subject "Rich" --body "Plain fallback" --html-body-file rich.html
"""

import argparse
import json
import os
import sys
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import smtplib
from typing import List, Optional


_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_CONFIG = os.path.join(_SKILL_ROOT, 'config', 'email_config.json')
_AGENTS_CONFIG = os.path.join(os.path.expanduser('~'), '.agents', 'config', 'email-notify.json')
_LEGACY_CONFIG = os.path.join(os.path.expanduser('~'), '.config', 'windsurf', 'email_config.json')


def _load_config() -> dict:
    """Load SMTP config, lowest priority first, so later files override earlier ones."""
    cfg = {}

    # Lowest priority first: local fallback, then the legacy path, then the
    # preferred ~/.agents/config path.
    for path in [_LOCAL_CONFIG, _LEGACY_CONFIG, _AGENTS_CONFIG]:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))

    # Environment variables (highest priority)
    env_map = {
        'smtp_host':   'EMAIL_SMTP_HOST',
        'smtp_port':   'EMAIL_SMTP_PORT',
        'from_addr':   'EMAIL_FROM_ADDR',
        'sender_name': 'EMAIL_SENDER_NAME',
    }
    for key, env_var in env_map.items():
        val = os.environ.get(env_var)
        if val:
            cfg[key] = val

    return cfg


def _parse_emails(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [v.strip() for v in raw.split(',') if v.strip()]


def send_mail(
    subject: str,
    body: str,
    to_emails: List[str],
    cc_emails: Optional[List[str]] = None,
    attachments: Optional[List[str]] = None,
    html_body: Optional[str] = None,
    config_path: Optional[str] = None
) -> bool:
    """Send an email, optionally as multipart/alternative with an HTML part.

    When html_body is given the message carries both a text/plain part (body)
    and a text/html part, so clients that cannot render HTML fall back to text.
    """
    if not to_emails:
        raise ValueError("to_emails is required")

    cfg = _load_config()
    if config_path and os.path.isfile(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg.update(json.load(f))

    smtp_host = cfg.get('smtp_host', '')
    smtp_port = int(cfg.get('smtp_port', 25))
    from_addr = cfg.get('from_addr', '')
    sender_name = cfg.get('sender_name', 'AI Cowork Kit')

    if not smtp_host:
        print('[✗] smtp_host not configured. Set EMAIL_SMTP_HOST or email_config.json')
        return False
    if not from_addr:
        print('[✗] from_addr not configured. Set EMAIL_FROM_ADDR or email_config.json')
        return False

    if html_body:
        body_part = MIMEMultipart('alternative')
        if body:
            body_part.attach(MIMEText(body, 'plain', 'utf-8'))
        body_part.attach(MIMEText(html_body, 'html', 'utf-8'))
    else:
        body_part = MIMEText(body, 'plain', 'utf-8')

    all_recipients = list(to_emails) + (list(cc_emails) if cc_emails else [])

    msg = MIMEMultipart('mixed') if attachments else body_part
    msg['From'] = formataddr((sender_name, from_addr))
    msg['To'] = ', '.join(to_emails)
    if cc_emails:
        msg['Cc'] = ', '.join(cc_emails)
    msg['Subject'] = subject

    if attachments:
        msg.attach(body_part)
        for path in attachments:
            if not path:
                continue
            if not os.path.exists(path):
                print(f'[✗] Attachment not found: {path}')
                return False
            with open(path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
            msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.sendmail(from_addr, all_recipients, msg.as_string())
        print(f'[✓] Email sent to {", ".join(all_recipients)}: {subject}')
        return True
    except Exception as e:
        print(f'[✗] Send failed: {e}')
        return False


def cmd_send(args: argparse.Namespace) -> int:
    """Handle the `send` subcommand: read the body/bodies, then send."""
    body = args.body or ''
    if args.body_file:
        with open(args.body_file, 'r', encoding='utf-8', errors='ignore') as f:
            body = f.read()

    html_body = args.html_body or ''
    if args.html_body_file:
        with open(args.html_body_file, 'r', encoding='utf-8', errors='ignore') as f:
            html_body = f.read()

    return 0 if send_mail(
        subject=args.subject,
        body=body,
        to_emails=_parse_emails(args.to),
        cc_emails=_parse_emails(args.cc),
        attachments=args.attach or [],
        html_body=html_body or None,
        config_path=args.config,
    ) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='send_email.py', description='Send email via SMTP')
    p.add_argument('--config', default=None, help='Path to email_config.json (optional override)')
    sub = p.add_subparsers(dest='command', required=True)

    s = sub.add_parser('send', help='Send an email (plain text or HTML) with optional attachments')
    s.add_argument('--to', required=True, help='Comma-separated recipients')
    s.add_argument('--cc', default='', help='Comma-separated CC recipients')
    s.add_argument('--subject', required=True)
    g = s.add_mutually_exclusive_group()
    g.add_argument('--body', default=None, help='Email body text')
    g.add_argument('--body-file', default=None, help='Read body from a file (e.g. report.md)')
    hg = s.add_mutually_exclusive_group()
    hg.add_argument('--html-body', default=None, help='HTML body; sent as multipart/alternative with --body')
    hg.add_argument('--html-body-file', default=None, help='Read HTML body from a file')
    s.add_argument('--attach', action='append', default=[], metavar='FILE', help='Attachment path (repeatable)')
    s.set_defaults(func=cmd_send)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
