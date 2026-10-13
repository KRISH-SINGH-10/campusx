import os

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "hackathon-511418")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

APP_NAME = "ClaimClear"
APP_TAGLINE = "Know what your insurer will pay, and why, before discharge"
