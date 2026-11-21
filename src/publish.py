"""Status=Designed wali aaj ki posts Instagram/Facebook par publish karta hai."""
import time

import requests

from . import config, meta, sheets


def wait_for_url(url, tries=24):
    for _ in range(tries):
        try:
            if requests.head(url, timeout=15, allow_redirects=True).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(10)
    return False


def main():
    bk = sheets.book()
    ws = sheets.posts_ws(bk)
    today = config.today()

    for r in sheets.read_posts(ws):
        if config.norm_date(r.get("Date")) != today or r.get("Status") != "Designed":
            continue
        row = r["_row"]
        urls = str(r.get("ImageURL", "")).split()
        url = urls[0] if urls else ""
        plat = (r.get("Platform") or "Both").strip().lower()
        tags = r.get("Hashtags", "").split()
        ig_caption = f"{r.get('Caption', '')}\n\n{' '.join(tags)}".strip()
        fb_caption = f"{r.get('Caption', '')}\n\n{' '.join(tags[:5])}".strip()

        if not urls or not all(wait_for_url(u) for u in urls):
            sheets.update_row(ws, row, Status="Failed", Notes="Image URL khula nahi (repo public hai?)")
            continue

        links, errors = [], []
        if plat in ("instagram", "both"):
            try:
                links.append(meta.publish_instagram(url, ig_caption) if len(urls) == 1
                             else meta.publish_instagram_carousel(urls, ig_caption))
            except Exception as e:
                errors.append(f"IG: {str(e)[:150]}")
        if plat in ("facebook", "both"):
            try:
                links.append(meta.publish_facebook(url, fb_caption) if len(urls) == 1
                             else meta.publish_facebook_multi(urls, fb_caption))
            except Exception as e:
                errors.append(f"FB: {str(e)[:150]}")

        if links and not errors:
            status = "Published"
        elif links:
            status = "Partial"
        else:
            status = "Failed"
        sheets.update_row(ws, row, Status=status, PostLink=" | ".join(links),
                          Notes=" ; ".join(errors) or r.get("Notes", ""))
        print(f"Row {row}: {status}")


if __name__ == "__main__":
    main()
