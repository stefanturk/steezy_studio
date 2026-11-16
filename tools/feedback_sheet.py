#!/usr/bin/env python3
"""Read and clear the Steezy Studio feedback sheet.

    python3 tools/feedback_sheet.py list              # rows still marked "new"
    python3 tools/feedback_sheet.py list --all
    python3 tools/feedback_sheet.py done 3 5          # mark sheet rows 3 and 5 done
    python3 tools/feedback_sheet.py note 3 "fixed in 4f5573d"   # write a note, mark it done

Uses the same Google service account as Job Finder (it has the sheet shared with it).
Credentials stay where they are; pass --creds or set STEEZY_FEEDBACK_CREDS to point at the file.
Needs gspread and google-auth (already installed for Job Finder).
"""
import argparse
import os
import sys

SHEET_ID = "1lDVebM8azGpB6NgU3keLPhhWVR35HTr-405pFSsT3o4"
DEFAULT_CREDS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "job_finder", "credentials.json")
COLUMNS = ["time", "id", "status", "tool", "version", "os", "note", "log"]
STATUS_COL = COLUMNS.index("status") + 1
# a note written back by a person or Claude goes in column I (after the log)
REPLY_COL = len(COLUMNS) + 1
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def open_sheet(creds_path, gspread=None, credentials=None):
    if gspread is None:
        import gspread
    if credentials is None:
        from google.oauth2.service_account import Credentials as credentials
    creds = credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SHEET_ID).sheet1


def rows(sheet, include_done=False):
    """[(sheet row number, {column: value})] for rows below the header."""
    out = []
    for n, values in enumerate(sheet.get_all_values(), start=1):
        if n == 1:
            continue
        rec = dict(zip(COLUMNS, values + [""] * len(COLUMNS)))
        if include_done or rec["status"].strip().lower() in ("", "new"):
            out.append((n, rec))
    return out


def show(found):
    if not found:
        print("No new feedback.")
    for n, r in found:
        print("row %d  [%s]  %s  v%s  %s  (%s)" % (n, r["status"] or "new", r["tool"], r["version"], r["os"], r["time"]))
        print("   " + r["note"].replace("\n", "\n   "))
        if r["log"]:
            print("   log: %d chars (use the sheet to read it)" % len(r["log"]))
        print()


def main(argv=None, sheet=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--creds", default=os.environ.get("STEEZY_FEEDBACK_CREDS", DEFAULT_CREDS))
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--all", action="store_true")
    dn = sub.add_parser("done")
    dn.add_argument("rows", nargs="+", type=int)
    nt = sub.add_parser("note")
    nt.add_argument("row", type=int)
    nt.add_argument("text")
    a = ap.parse_args(argv)
    sheet = sheet or open_sheet(a.creds)
    if a.cmd == "list":
        show(rows(sheet, a.all))
    elif a.cmd == "done":
        for n in a.rows:
            sheet.update_cell(n, STATUS_COL, "done")
        print("Marked done: " + ", ".join(map(str, a.rows)))
    else:
        sheet.update_cell(a.row, REPLY_COL, a.text)
        sheet.update_cell(a.row, STATUS_COL, "done")
        print("Row %d noted and marked done." % a.row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
