#!/usr/bin/env python3
"""Email the weekly digest. Cron: 0 8 * * 1  cd /path/to/app && .venv/bin/python scripts/send_digest.py
Requires env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, DIGEST_TO (comma-separated), DIGEST_FROM."""
import os, smtplib, sys
from email.mime.text import MIMEText
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.main import _digest_data
d = _digest_data()
lines = [f"AVL Manager weekly digest (since {d['since']})", ""]
lines.append(f"Status changes: {len(d['changes'])}")
for r in d["changes"]:
    lines.append(f"  {r['ts'][:10]}  {r['avl_name']}: {r['product']}  {r['old_status'] or '-'} -> {r['new_status']}")
lines.append(f"\nCalls held: {len(d['calls'])}")
for r in d["calls"]:
    lines.append(f"  {r['call_date']}  {r['avl_name']} ({r['call_type']}): {r['topics']}")
lines.append(f"\nOverdue actions: {len(d['overdue'])}")
for r in d["overdue"]:
    lines.append(f"  DUE {r['due_date']}  {r['description']} ({r['owner']}, {r['avl_name'] or '-'})")
body = "\n".join(lines)
msg = MIMEText(body)
msg["Subject"] = "Qcells AVL Manager - weekly digest"
msg["From"] = os.environ["DIGEST_FROM"]
msg["To"] = os.environ["DIGEST_TO"]
with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
    s.starttls(); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
    s.send_message(msg)
print("digest sent")
