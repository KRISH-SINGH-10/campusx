import os

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "hackathon-511418")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DOCS_BUCKET = os.getenv("DOCS_BUCKET", f"{PROJECT_ID}-claimclear-docs")

APP_NAME = "ClaimClear"
APP_TAGLINE = "Know what your insurer will pay, and why, before discharge"
