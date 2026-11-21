"""Aaj ki post: Sheet -> caption/hashtags -> safety check -> AI design (+critic) -> Status=Designed."""
import os
import re
from datetime import datetime

from . import ai, config, designer, sheets

HOLD = {"TRUE", "YES", "Y", "1", "X", "HOLD"}
IMG_DIR = designer.design.ROOT / "images"


def clean_old_images(keep_days=10):
    for f in IMG_DIR.glob("*.jpg"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m and (datetime.now() - datetime.strptime(m.group(1), "%Y-%m-%d")).days > keep_days:
            f.unlink()


def slide_count(r):
    try:
        n = int(str(r.get("Slides", "")).strip() or 0)
    except ValueError:
        n = 0
    if n <= 0 and str(r.get("Topic", "")).strip().lower().startswith("carousel"):
        n = 5
    return max(1, min(n, 8))


def main():
    bk = sheets.book()
    brand = sheets.get_brand(bk)
    ws = sheets.posts_ws(bk)
    today = config.today()
    repo = os.environ.get("GITHUB_REPOSITORY", "USER/REPO")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    done = 0

    for r in sheets.read_posts(ws):
        if config.norm_date(r.get("Date")) != today:
            continue
        if str(r.get("Status", "")).strip() not in ("", "Pending"):
            continue
        row = r["_row"]
        if str(r.get("Hold", "")).strip().upper() in HOLD:
            sheets.update_row(ws, row, Status="Held", Notes="Hold tick tha")
            continue
        try:
            n = slide_count(r)
            notes = ai.research(brand, r)
            d = ai.build_post(brand, r, notes, n)
            caption = d["caption"].strip()
            verdict = ai.safety_check(brand, d["headline"] + " " + " ".join(
                s.get("title", "") + " " + s.get("body", "") for s in (d.get("slides") or [])), caption)
            if not verdict.get("safe", False):
                sheets.update_row(ws, row, Status="Held", Caption=caption,
                                  Notes="AI safety: " + str(verdict.get("reason", ""))[:200])
                print(f"Row {row}: Held (safety)")
                continue
            stem = f"{today}-r{row}"
            paths = designer.make_slides(brand, r, d, IMG_DIR, stem, datetime.now().timetuple().tm_yday)
            base = f"https://raw.githubusercontent.com/{repo}/{branch}/images/"
            urls = " ".join(base + p.name for p in paths)
            sheets.update_row(ws, row, Status="Designed", Caption=caption,
                              Hashtags=" ".join(d["hashtags"]), ImageURL=urls,
                              Notes="Keywords: " + ", ".join(d.get("keywords", [])))
            print(f"Row {row}: Designed ({len(paths)} image)")
            done += 1
        except Exception as e:
            sheets.update_row(ws, row, Status="Failed", Notes=f"Generate: {type(e).__name__}: {str(e)[:150]}")
            print(f"Row {row}: Failed {type(e).__name__}")

    clean_old_images()
    print(f"Designed: {done}")


if __name__ == "__main__":
    main()
