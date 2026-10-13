"""Demo sign-in with two roles. Accounts are seeded from demo_accounts.json;
the session lives in a signed cookie."""
import hmac
import json
import secrets
from pathlib import Path

from fastapi import HTTPException, Request

from app.services import db

ACCOUNTS = json.loads((Path(__file__).parent / "demo_accounts.json").read_text(encoding="utf-8"))


def session_secret() -> str:
    """One signing key shared by every instance and kept across deploys, stored
    in Firestore so it never sits in the repository."""
    doc = db.get("config", "session")
    if doc and doc.get("secret"):
        return doc["secret"]
    secret = secrets.token_urlsafe(48)
    db.put("config", "session", {"secret": secret})
    return secret


def check(email: str, password: str) -> dict | None:
    for a in ACCOUNTS:
        if a["email"] == email.strip().lower() and hmac.compare_digest(a["password"], password):
            return {"email": a["email"], "role": a["role"], "name": a["name"]}
    return None


def current(request: Request) -> dict | None:
    return request.session.get("user")


def require(request: Request, role: str | None = None) -> dict:
    user = current(request)
    if not user:
        raise HTTPException(401, "Please sign in.")
    if role and user["role"] != role:
        raise HTTPException(403, "This page is not available for your account.")
    return user


def can_see(user: dict, claim: dict) -> bool:
    return user["role"] == "insurer" or claim.get("owner") == user["email"]
