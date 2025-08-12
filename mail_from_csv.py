#!/usr/bin/env python3
import argparse, base64, csv, mimetypes, sys, time, re
from pathlib import Path
from email.message import EmailMessage
from string import Template

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def load_template(value: str) -> str:
    if value and value.startswith("@"):
        return Path(value[1:]).read_text(encoding="utf-8")
    return value or ""

def normalize_placeholders(tpl: str) -> str:
    # Convert {name} to $name ONLY for simple identifiers to avoid clashing with CSS like {.class{...}}
    # Matches {firstname}, {company}, but NOT {display:none} or {color: red;}
    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", r"$\1", tpl)

class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"

def render(tpl: str, row: dict) -> str:
    norm = normalize_placeholders(tpl)
    return Template(norm).safe_substitute(row)

def get_service():
    token_path = Path("token.json")
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

def add_attachments(msg: EmailMessage, paths):
    for p in paths:
        p = (p or "").strip()
        if not p:
            continue
        fp = Path(p).expanduser()
        if not fp.exists():
            print(f"[warn] attachment not found: {fp}", file=sys.stderr)
            continue
        ctype, encoding = mimetypes.guess_type(fp.name)
        maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "octet-stream"))
        msg.add_attachment(fp.read_bytes(), maintype=maintype, subtype=subtype, filename=fp.name)

def send_one(service, message: EmailMessage, retries=5):
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    for attempt in range(retries):
        try:
            return service.users().messages().send(userId="me", body={"raw": raw}).execute()
        except HttpError as e:
            status = getattr(e, "status_code", None)
            if not status and hasattr(e, "resp") and hasattr(e.resp, "status"):
                status = e.resp.status
            if status in (403, 429, 500, 502, 503):
                sleep_s = 2 ** attempt
                print(f"[retry] status {status}. Sleeping {sleep_s}s …", file=sys.stderr)
                time.sleep(sleep_s)
                continue
            raise

def main():
    ap = argparse.ArgumentParser(description="Send Gmail from CSV (Gmail API OAuth).")
    ap.add_argument("--csv", required=True, help="Path to recipients CSV")
    ap.add_argument("--subject", required=True, help="Subject text or @file.txt with {placeholders} or $placeholders")
    ap.add_argument("--html", required=True, help="HTML body or @file.html with {placeholders} or $placeholders")
    ap.add_argument("--text", help="Optional plain-text body or @file.txt")
    ap.add_argument("--sender", default="me", help='Sender. Use "me" for the authorized account (default).')
    ap.add_argument("--col_to", default="email", help="CSV column for recipient email (default: email)")
    ap.add_argument("--col_cc", default="cc", help="CSV column for CC (optional)")
    ap.add_argument("--col_bcc", default="bcc", help="CSV column for BCC (optional)")
    ap.add_argument("--attach", default="", help="Common attachment path(s), comma-separated")
    ap.add_argument("--col_attach", default="attachment", help="CSV column with attachment path(s), comma-separated")
    ap.add_argument("--limit", type=int, default=0, help="Send to first N rows only (0 = all)")
    ap.add_argument("--dry_run", action="store_true", help="Print previews; do not send")
    args = ap.parse_args()

    subject_tpl = load_template(args.subject)
    html_tpl = load_template(args.html)
    text_tpl = load_template(args.text) if args.text else None
    common_attach = [a.strip() for a in args.attach.split(",")] if args.attach else []

    service = get_service()
    sent = 0

    with open(args.csv, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            if args.limit and sent >= args.limit:
                break

            to_addr = (row.get(args.col_to) or row.get("email") or "").strip()
            if not to_addr:
                print(f"[skip] row {i}: missing recipient address", file=sys.stderr)
                continue

            subject = render(subject_tpl, row)
            html = render(html_tpl, row)
            text = render(text_tpl, row) if text_tpl else None

            msg = EmailMessage()
            msg["To"] = to_addr
            if args.sender != "me":
                msg["From"] = args.sender
            msg["Subject"] = subject

            cc = (row.get(args.col_cc) or "").strip()
            bcc = (row.get(args.col_bcc) or "").strip()
            if cc:  msg["Cc"] = cc
            if bcc: msg["Bcc"] = bcc

            if text:
                msg.set_content(text)
                msg.add_alternative(html, subtype="html")
            else:
                msg.set_content(html, subtype="html")

            row_attachments = []
            if args.col_attach in row and row[args.col_attach].strip():
                row_attachments = [p.strip() for p in row[args.col_attach].split(",")]
            add_attachments(msg, common_attach + row_attachments)

            if args.dry_run:
                print(f"\n--- DRY RUN row {i} ---")
                print("To:", to_addr)
                if cc: print("Cc:", cc)
                if bcc: print("Bcc:", bcc)
                preview_source = text if text else html
                preview = (preview_source or "").replace("\n", " ")
                print("Subject:", subject)
                print("Body preview:", (preview[:200] + "…") if len(preview) > 200 else preview)
                continue

            send_one(service, msg)
            sent += 1
            time.sleep(0.2)

    print(f"Done. Sent {sent} message(s).")

if __name__ == "__main__":
    main()
