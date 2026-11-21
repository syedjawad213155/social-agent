import json
import os

import gspread
from gspread.utils import rowcol_to_a1

LOG_HEADER = ["Time", "Platform", "Type", "ItemID", "Author", "Message",
              "Category", "Action", "Reply"]


def book():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    gc = gspread.service_account_from_dict(info)
    return gc.open_by_key(os.environ["SHEET_ID"])


def get_brand(bk):
    brand = {}
    for row in bk.worksheet("Brand").get_all_values()[1:]:
        if len(row) >= 2 and row[0].strip():
            brand[row[0].strip()] = row[1].strip()
    return brand


def get_faq(bk):
    lines = []
    for row in bk.worksheet("FAQ").get_all_values()[1:]:
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            lines.append(f"Q: {row[0].strip()}\nA: {row[1].strip()}")
    return "\n\n".join(lines)


def posts_ws(bk):
    return bk.worksheet("Posts")


def read_posts(ws):
    """Har row dict ban kar aati hai, saath '_row' (sheet ka row number)."""
    rows = ws.get_all_records()
    for i, r in enumerate(rows):
        r["_row"] = i + 2
    return rows


def update_row(ws, rownum, **vals):
    headers = ws.row_values(1)
    batch = []
    for key, val in vals.items():
        if key in headers:
            col = headers.index(key) + 1
            batch.append({"range": rowcol_to_a1(rownum, col), "values": [[val]]})
    if batch:
        ws.batch_update(batch)


def log_ws(bk):
    try:
        return bk.worksheet("Inbox_Log")
    except gspread.WorksheetNotFound:
        ws = bk.add_worksheet("Inbox_Log", rows=1000, cols=len(LOG_HEADER))
        ws.append_row(LOG_HEADER)
        return ws
