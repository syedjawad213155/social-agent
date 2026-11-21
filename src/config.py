import os
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Karachi"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
GRAPH_VERSION = os.getenv("GRAPH_VERSION") or "v23.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
DRY_RUN = os.getenv("DRY_RUN", "0").strip() == "1"
MAX_REPLIES = int(os.getenv("MAX_REPLIES", "8"))          # har run mein zyada se zyada replies
COMMENT_MAX_AGE_H = int(os.getenv("COMMENT_MAX_AGE_H", "72"))
DM_MAX_AGE_H = 23                                          # Meta ki 24 ghante ki window


def now():
    return datetime.now(TZ)


def today():
    return now().strftime("%Y-%m-%d")


def norm_date(value):
    """Sheet ki date ko YYYY-MM-DD mein badalta hai."""
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""
