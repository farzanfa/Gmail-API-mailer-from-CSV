# Gmail Mail from CSV (Python + Gmail API)

## 1) Prepare Google OAuth credentials (one-time)
1. Go to Google Cloud Console → Create Project (or use an existing one).
2. APIs & Services → **Enable APIs & Services** → search **Gmail API** → Enable.
3. APIs & Services → **OAuth consent screen**:
   - User type: **External** (Testing is fine).
   - Add your Gmail address under **Test users**.
4. **Credentials** → **Create Credentials** → **OAuth client ID** → **Desktop app**.
5. Download the file as **credentials.json** and place it next to this README.

## 2) Install locally
```bash
make install
# or
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 3) First-run to authorise
```bash
make auth
```
- A browser opens → pick your Gmail/Workspace account → allow the **gmail.send** scope.
- This creates **token.json** for future runs.

## 4) Edit your CSV/templates
- `recipients.csv` columns: `email, firstname, company, cc, bcc, attachment`
- Edit `subject.txt` and `body.html` and use placeholders like `{firstname}` and `{company}`.
- Per-recipient attachments: put absolute paths in the CSV `attachment` column (comma-separated for multiple).

## 5) Dry run and send
```bash
make dryrun   # previews only
make send     # actually sends
```

### Direct Python usage
```bash
. .venv/bin/activate
python mail_from_csv.py --csv recipients.csv --subject @subject.txt --html @body.html --dry_run
python mail_from_csv.py --csv recipients.csv --subject @subject.txt --html @body.html
```

## Notes
- If headless (no browser), edit the script and replace `run_local_server(...)` with `run_console()`.
- Respect Gmail/Workspace daily sending limits.
- Add `credentials.json` and `token.json` to `.gitignore` if committing this folder.
