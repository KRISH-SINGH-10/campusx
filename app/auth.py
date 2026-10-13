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


# The customer side and the insurer side are separate portals with separate sign-ins,
# so one browser can hold a customer in one tab and an insurer in another.
PORTALS = ("customer", "insurer")


def _sessions(request: Request) -> dict:
    legacy = request.session.pop("user", None)  # sessions from before the portals were split
    if legacy:
        request.session.setdefault(legacy["role"], legacy)
    return request.session


def sign_in(request: Request, user: dict) -> None:
    _sessions(request)[user["role"]] = user


def sign_out(request: Request, portal: str) -> None:
    _sessions(request).pop(portal, None)


def current(request: Request, portal: str) -> dict | None:
    return _sessions(request).get(portal)


def signed_in(request: Request) -> list[dict]:
    return [u for u in (current(request, p) for p in PORTALS) if u]


def portal_of(request: Request) -> str:
    """Which portal a shared API call comes from: the page says so in a header
    (or a query parameter on plain links); otherwise infer it from who is signed in."""
    asked = request.headers.get("x-portal") or request.query_params.get("portal")
    if asked in PORTALS:
        return asked
    present = [u["role"] for u in signed_in(request)]
    return present[0] if len(present) == 1 else "customer"


def require(request: Request, role: str | None = None) -> dict:
    user = current(request, role or portal_of(request))
    if user:
        return user
    if role and signed_in(request):
        raise HTTPException(403, "This page is not available for your account.")
    raise HTTPException(401, "Please sign in.")


def can_see(user: dict, claim: dict) -> bool:
    return user["role"] == "insurer" or claim.get("owner") == user["email"]
