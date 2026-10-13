"""Sign-in with two roles. Demo accounts are seeded from demo_accounts.json;
customers can also register, and are stored in Firestore with a salted password hash.
The session lives in a signed cookie."""
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path

from fastapi import HTTPException, Request

from app.services import db

ACCOUNTS = json.loads((Path(__file__).parent / "demo_accounts.json").read_text(encoding="utf-8"))
USERS = "users"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ITERATIONS = 200_000


def session_secret() -> str:
    """One signing key shared by every instance and kept across deploys, stored
    in Firestore so it never sits in the repository."""
    doc = db.get("config", "session")
    if doc and doc.get("secret"):
        return doc["secret"]
    secret = secrets.token_urlsafe(48)
    db.put("config", "session", {"secret": secret})
    return secret


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()


def _user_id(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()[:40]


def register(name: str, email: str, password: str) -> dict:
    """Create a customer account. Insurer accounts are never self-registered."""
    name, email = " ".join(name.split()), email.strip().lower()
    if len(name) < 2:
        raise HTTPException(400, "Enter your full name.")
    if not _EMAIL.match(email):
        raise HTTPException(400, "Enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(400, "Choose a password of at least 8 characters.")
    if any(a["email"] == email for a in ACCOUNTS) or db.get(USERS, _user_id(email)):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    salt = secrets.token_hex(16)
    db.put(USERS, _user_id(email), {"name": name, "email": email, "salt": salt,
                                     "password_hash": _hash(password, salt), "role": "customer"})
    return {"email": email, "role": "customer", "name": name, "demo": False}


def check(email: str, password: str) -> dict | None:
    email = email.strip().lower()
    for a in ACCOUNTS:
        if a["email"] == email and hmac.compare_digest(a["password"], password):
            return {"email": a["email"], "role": a["role"], "name": a["name"], "demo": True}
    user = db.get(USERS, _user_id(email))
    if user and hmac.compare_digest(user["password_hash"], _hash(password, user["salt"])):
        return {"email": user["email"], "role": user["role"], "name": user["name"], "demo": False}
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
