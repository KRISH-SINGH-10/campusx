# Run the app locally at http://localhost:8765 with auto-reload.
$env:GOOGLE_CLOUD_PROJECT = "hackathon-511418"
& "$env:USERPROFILE\cx-venv\Scripts\python.exe" -W ignore::FutureWarning -m uvicorn app.main:app --reload --port 8765
