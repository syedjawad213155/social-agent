"""Sirf Facebook Comments + DMs: naye items dhoondo, jawab do, mushkil wale 'Needs Human' mark karo.
Privacy: customers ke messages public Actions logs mein print nahi hote."""
import time
from datetime import datetime, timezone

from . import ai, config, meta, sheets


def age_hours(ts):
    try:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
        return (datetime.now(timezone.utc) - t).total_seconds() / 3600
    except Exception:
        return 9999


def collect():
    items, errors = [], []
    pid = meta.page_id()

    def safe(label, fn):
        try:
            fn()
        except Exception as e:
            errors.append(f"{label}: {str(e)[:120]}")

    def fb_comments():
        for p in meta.fb_recent_posts():
            for c in meta.fb_comments(p["id"]):
                frm = c.get("from", {})
                if frm.get("id") == pid:
                    continue
                replied = any(
                    x.get("from", {}).get("id") == pid
                    for x in c.get("comments", {}).get("data", [])
                )
                if replied or age_hours(c.get("created_time", "")) > config.COMMENT_MAX_AGE_H:
                    continue
                items.append(
                    dict(
                        platform="Facebook",
                        kind="comment",
                        id=c["id"],
                        text=c.get("message", ""),
                        author=frm.get("name", ""),
                        ts=c.get("created_time", ""),
                    )
                )

    def fb_dms():
        for conv in meta.conversations("messenger"):
            msgs = conv.get("messages", {}).get("data", [])
            if not msgs:
                continue
            m = msgs[0]
            frm = m.get("from", {})
            if frm.get("id") == pid:
                continue  # aakhri message hamara hai -> jawab ho chuka
            if age_hours(m.get("created_time", "")) > config.DM_MAX_AGE_H:
                continue
            items.append(
                dict(
                    platform="Facebook",
                    kind="dm",
                    id=m["id"],
                    text=m.get("message", ""),
                    author=frm.get("name", ""),
                    sender_id=frm.get("id"),
                    ts=m.get("created_time", ""),
                    dm_platform="messenger",
                )
            )

    safe("FB comments", fb_comments)
    safe("FB DMs", fb_dms)
    return items, errors


def send(it, text):
    if it["kind"] == "dm":
        meta.send_dm(it["dm_platform"], it["sender_id"], text)
    else:
        meta.fb_reply_comment(it["id"], text)


def main():
    bk = sheets.book()
    brand, faq = sheets.get_brand(bk), sheets.get_faq(bk)
    log = sheets.log_ws(bk)
    seen = set(log.col_values(4))
    keywords = [
        k.strip().lower()
        for k in brand.get("escalation_keywords", "").split(",")
        if k.strip()
    ]
    safe_dm = brand.get(
        "safe_reply_dm", "Thanks for reaching out. Our team will contact you shortly."
    )
    safe_cm = brand.get(
        "safe_reply_comment", "Thanks! Please DM us and our team will help you."
    )

    items, errors = collect()
    items = [i for i in items if i["id"] not in seen and i["text"].strip()]
    items.sort(key=lambda i: i["ts"])
    print(f"Naye items: {len(items)} | collect errors: {errors}")

    budget, rows = config.MAX_REPLIES, []
    for it in items:
        if budget <= 0:
            print("Reply limit poori, baaqi agli run mein")
            break
        text = it["text"]
        category, action, reply = "", "", ""
        try:
            if any(k in text.lower() for k in keywords):
                category, needs_human, reply = "sensitive", True, ""
            else:
                res = ai.triage(brand, faq, it["kind"], text, it["author"])
                category = res.get("category", "other")
                needs_human = bool(res.get("needs_human"))
                reply = (res.get("reply") or "").strip()
                time.sleep(5)  # Gemini free rate limit

            if category == "spam":
                action = "Ignored"
            elif needs_human:
                reply = safe_dm if it["kind"] == "dm" else safe_cm
                action = "Needs Human"
            elif reply:
                action = "Replied"
            else:
                action = "Ignored"

            if action != "Ignored":
                if config.DRY_RUN:
                    action += " (DRY RUN - bheja nahi)"
                else:
                    send(it, reply)
                budget -= 1
        except Exception as e:
            action, reply = f"Error: {type(e).__name__}", str(e)[:150]
            print("Item fail:", type(e).__name__)
        rows.append(
            [
                config.now().strftime("%Y-%m-%d %H:%M"),
                it["platform"],
                it["kind"],
                it["id"],
                it["author"],
                text[:500],
                category,
                action,
                reply,
            ]
        )

    if rows:
        log.append_rows(rows)
    print(f"Logged: {len(rows)}")


if __name__ == "__main__":
    main()
