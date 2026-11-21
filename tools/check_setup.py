"""Setup check: har cheez theek jur gayi ya nahi. GitHub Actions se 'Setup Check' chalayein."""
import sys

sys.path.insert(0, ".")
from src import ai, meta, sheets  # noqa: E402

ok_all = True


def step(name, fn):
    global ok_all
    try:
        print(f"✅ {name}: {fn()}")
    except Exception as e:
        ok_all = False
        print(f"❌ {name}: {type(e).__name__}: {str(e)[:200]}")


bk = None


def sheet():
    global bk
    bk = sheets.book()
    names = [w.title for w in bk.worksheets()]
    missing = [t for t in ("Posts", "Brand", "FAQ") if t not in names]
    if missing:
        raise RuntimeError(f"Tabs missing: {missing}")
    return f"Sheet '{bk.title}' khul gayi"


step("Google Sheet", sheet)
step("Brand tab", lambda: f"{len(sheets.get_brand(bk))} settings mili")
step("Gemini", lambda: ai.ask_json('Reply JSON {"ok": true}', temperature=0))
step("Facebook Page", lambda: meta.get(meta.page_id(), fields="name")["name"])
step("Instagram", lambda: "@" + meta.ig_username())
print("\nSab theek hai ✅" if ok_all else "\nUpar ❌ wali cheez theek karein.")
sys.exit(0 if ok_all else 1)
