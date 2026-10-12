import os

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "hackathon-511418")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

APP_NAME = "CampusX"
APP_TAGLINE = "Digital Campus on Google Cloud"
