# Social Media Agent v2 (AI Art Director, free, GitHub Actions)

Daily: Sheet -> Gemini caption/hashtags -> safety check -> AI Art Director designs (HTML/CSS/SVG)
-> Gemini critic reviews the screenshot and requests fixes -> publish (single image or carousel) to Instagram + Facebook.
Every 15 min: reply to comments and DMs; sensitive ones are marked "Needs Human" in Inbox_Log.

Secrets: GEMINI_API_KEY, GOOGLE_SERVICE_ACCOUNT_JSON, SHEET_ID, PAGE_ACCESS_TOKEN, PAGE_ID, IG_USER_ID
Variables (optional): DRY_RUN, GEMINI_MODEL, DESIGN_MODEL, DESIGN_ROUNDS

Optional Brand-tab keys: design_style (free-text look you want), design_mode (ai | template),
use_ai_background (yes/no).  Optional Posts column: Slides (2-8) for carousels; Topics starting with
"Carousel" default to 5 slides.
Repo must be PUBLIC (Instagram needs a public image URL).
