import os

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "hackathon-511418")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DOCS_BUCKET = os.getenv("DOCS_BUCKET", f"{PROJECT_ID}-claimclear-docs")
# K_SERVICE is set by Cloud Run; cookies are HTTPS-only there and plain on localhost.
ON_CLOUD_RUN = bool(os.getenv("K_SERVICE"))
# Demo build: the sign-in page offers the seeded accounts. Set to 0 to hide them.
SHOW_DEMO_ACCOUNTS = os.getenv("SHOW_DEMO_ACCOUNTS", "1") == "1"

APP_NAME = "ClaimClear"
APP_TAGLINE = "Know what your insurer will pay, and why, before discharge"
