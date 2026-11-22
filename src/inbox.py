"""Sirf Facebook Comments + DMs: naye items dhoondo, jawab do, mushkil wale 'Needs Human' mark karo.
Privacy: customers ke messages public Actions logs mein print nahi hote."""
import time
from datetime import datetime, timezone

from . import ai, config, meta, sheets


def log_step(msg):
    print(msg, flush=True)


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
        log_step("Fetching FB posts...")
        posts = meta.fb_recent_posts()
        log_step(f"FB posts count: {len(posts)}")
        for p in posts:
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
        log_step("Fetching FB DMs...")
        convs = meta.conversations("messenger")
        log_step(f"FB conversations count: {len(convs)}")
        for conv in convs:
            msgs = conv.get("messages", {}).get("data", [])
            if not msgs:
                continue
            m = msgs[0]
            frm = m.get("from", {})
            if frm.get("id") == pid:
                continue
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
    log_step("Opening Google Sheet...")
    bk = sheets.book()
    log_step("Reading brand, FAQ, and log...")
    brand, faq = sheets.get_brand(bk), sheets.get_faq(bk)
    log_ws = sheets.log_ws(bk)
    seen = set(log_ws.col_values(4))
    log_step(f"Seen IDs count: {len(seen)}")

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
    log_step(f"Naye items: {len(items)} | collect errors: {errors}")

    budget, rows = config.MAX_REPLIES, []
    for idx, it in enumerate(items, start=1):
        if budget <= 0:
            log_step("Reply limit poori, baaqi agli run mein")
            break
        log_step(f"Processing item {idx}/{len(items)} ({it['kind']})...")
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
                time.sleep(1)

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
            log_step(f"Item fail: {type(e).__name__}")
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
        log_step(f"Appending {len(rows)} rows to sheet...")
        log_ws.append_rows(rows)
    log_step(f"Logged: {len(rows)}")


if __name__ == "__main__":
    main()
