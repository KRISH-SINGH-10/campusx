from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from app import auth, config
from app.claims import service
from app.services import ai, db, storage

BASE = Path(__file__).parent
SAMPLES_DIR = BASE / "static" / "samples"
app = FastAPI(title=config.APP_NAME)
app.add_middleware(
    SessionMiddleware,
    secret_key=auth.session_secret(),
    session_cookie="claimclear_session",
    max_age=12 * 60 * 60,
    same_site="lax",
    https_only=config.ON_CLOUD_RUN,
)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

CLAIMS = service.CLAIMS
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOADS = {"image/png", "image/jpeg", "image/webp", "application/pdf"}

SAMPLE_POLICY = "policy-arogya-shield-gold.pdf"
SAMPLE_BILLS = {
    "appendix": {
        "file": "bill-1-appendix-within-limits.pdf",
        "title": "Appendix surgery",
        "blurb": "Room within the limit. A clean claim.",
    },
    "gallbladder": {
        "file": "bill-2-gallbladder-room-upgrade.pdf",
        "title": "Gallbladder surgery",
        "blurb": "Deluxe room above the cap, plus non-payable items.",
    },
    "cataract": {
        "file": "bill-3-cataract-sublimit.pdf",
        "title": "Cataract surgery",
        "blurb": "Bill is above the policy's cataract sub-limit.",
    },
}


def page(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        name,
        {
            "app_name": config.APP_NAME,
            "tagline": config.APP_TAGLINE,
            "user": auth.current(request),
            **ctx,
        },
    )


def _home_for(user: dict) -> str:
    return "/insurer" if user["role"] == "insurer" else "/"


def _page_guard(request: Request, role: str) -> RedirectResponse | None:
    """Pages redirect instead of returning an error: to sign-in, or to the user's own side."""
    user = auth.current(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != role:
        return RedirectResponse(_home_for(user), status_code=303)
    return None


# ---------- sign-in ----------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = auth.current(request)
    if user:
        return RedirectResponse(_home_for(user), status_code=303)
    demo = [a for a in auth.ACCOUNTS] if config.SHOW_DEMO_ACCOUNTS else []
    return page(request, "login.html", active="login", demo_accounts=demo)


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


@app.post("/api/login")
def login(request: Request, body: LoginIn):
    user = auth.check(body.email, body.password)
    if not user:
        raise HTTPException(401, "Email or password is incorrect.")
    request.session["user"] = user
    return {"redirect": _home_for(user)}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"redirect": "/login"}


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return _page_guard(request, "customer") or page(
        request, "index.html", active="home", samples=SAMPLE_BILLS, sample_policy=SAMPLE_POLICY
    )


@app.get("/claims/{claim_id}", response_class=HTMLResponse)
def claim_page(request: Request, claim_id: str):
    return _page_guard(request, "customer") or page(
        request, "claim.html", active="home", claim_id=claim_id, role="patient"
    )


@app.get("/insurer", response_class=HTMLResponse)
def insurer_queue(request: Request):
    return _page_guard(request, "insurer") or page(request, "insurer.html", active="insurer")


@app.get("/insurer/claims/{claim_id}", response_class=HTMLResponse)
def insurer_claim(request: Request, claim_id: str):
    return _page_guard(request, "insurer") or page(
        request, "claim.html", active="insurer", claim_id=claim_id, role="insurer"
    )


@app.get("/api/health")
def health():
    out = {"project": config.PROJECT_ID, "model": config.GEMINI_MODEL}
    try:
        db.list_all(CLAIMS, limit=1)
        out["firestore"] = "ok"
    except Exception as e:
        out["firestore"] = f"error: {str(e)[:200]}"
    try:
        ai.generate_text("Reply with exactly: ok")
        out["gemini"] = "ok"
    except Exception as e:
        out["gemini"] = f"error: {str(e)[:200]}"
    return out


# ---------- claims ----------

async def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    if file.content_type not in ALLOWED_UPLOADS:
        raise HTTPException(415, "Upload a PDF, PNG, JPEG, or WebP file.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    return data, file.content_type


@app.post("/api/claims", status_code=201)
async def claims_create(
    request: Request,
    sample: Optional[str] = Form(None),
    bill: Optional[UploadFile] = File(None),
    policy: Optional[UploadFile] = File(None),
):
    """Read both documents, run the decision engine, and store the claim."""
    user = auth.require(request, "customer")
    if sample:
        if sample not in SAMPLE_BILLS:
            raise HTTPException(400, "Unknown sample.")
        bill_doc = ((SAMPLES_DIR / SAMPLE_BILLS[sample]["file"]).read_bytes(), "application/pdf")
        policy_doc = ((SAMPLES_DIR / SAMPLE_POLICY).read_bytes(), "application/pdf")
    elif bill and policy:
        bill_doc = await _read_upload(bill)
        policy_doc = await _read_upload(policy)
    else:
        raise HTTPException(400, "Attach both the hospital bill and the policy document.")

    try:
        claim = service.create_claim(
            *bill_doc,
            *policy_doc,
            owner=user["email"],
            submitted_by=user["name"],
            sample_title=SAMPLE_BILLS[sample]["title"] if sample else None,
        )
    except Exception as e:
        raise HTTPException(502, f"Could not read the documents: {str(e)[:200]}")
    if not claim["bill"]["items"]:
        raise HTTPException(422, "No billed lines were found in the hospital bill.")
    return {"id": claim["id"]}


def _claim_for(request: Request, claim_id: str, role: str | None = None) -> dict:
    """The claim, if this user may see it. Other people's claims look like missing ones."""
    user = auth.require(request, role)
    claim = db.get(CLAIMS, claim_id)
    if not claim or not auth.can_see(user, claim):
        raise HTTPException(404, "Claim not found.")
    return claim


@app.get("/api/claims")
def claims_list(request: Request):
    user = auth.require(request)
    return [
        {
            "id": c["id"],
            "created_at": c.get("created_at"),
            "status": c.get("status"),
            "title": c.get("title") or c["bill"]["procedure"],
            "sample": c.get("sample", False),
            "patient_name": c["bill"]["patient_name"],
            "hospital_name": c["bill"]["hospital_name"],
            "procedure": c["bill"]["procedure"],
            "totals": c["result"]["totals"],
            "overbilling_count": c["result"].get("overbilling_count", 0),
        }
        for c in db.list_all(CLAIMS, limit=100)
        if auth.can_see(user, c)
    ]


@app.get("/api/claims/{claim_id}")
def claims_get(request: Request, claim_id: str):
    return _claim_for(request, claim_id)


class ExplainIn(BaseModel):
    language: Literal["English", "Hindi", "Marathi"] = "English"


@app.post("/api/claims/{claim_id}/explain")
def claims_explain(request: Request, claim_id: str, body: ExplainIn):
    claim = _claim_for(request, claim_id)
    try:
        return {"text": service.explain(claim, body.language)}
    except Exception as e:
        raise HTTPException(502, f"Could not write the explanation: {str(e)[:200]}")


@app.post("/api/claims/{claim_id}/appeal")
def claims_appeal(request: Request, claim_id: str, body: ExplainIn):
    claim = _claim_for(request, claim_id, "customer")
    try:
        return {"text": service.appeal_letter(claim, body.language)}
    except Exception as e:
        raise HTTPException(502, f"Could not draft the letter: {str(e)[:200]}")


@app.post("/api/claims/{claim_id}/review")
def claims_review(request: Request, claim_id: str):
    claim = _claim_for(request, claim_id, "insurer")
    try:
        return {"text": service.reviewer_summary(claim)}
    except Exception as e:
        raise HTTPException(502, f"Could not write the summary: {str(e)[:200]}")


@app.get("/api/claims/{claim_id}/documents/{kind}")
def claims_document(request: Request, claim_id: str, kind: Literal["bill", "policy"]):
    """Serve an original document from the private bucket."""
    name = (_claim_for(request, claim_id).get("documents") or {}).get(kind)
    if not name:
        raise HTTPException(404, "Document not stored for this claim.")
    try:
        data, mime_type = storage.load(name)
    except Exception as e:
        raise HTTPException(502, f"Could not open the document: {str(e)[:200]}")
    return Response(data, media_type=mime_type, headers={"Content-Disposition": "inline"})


class DecisionIn(BaseModel):
    status: Literal["approved", "queried", "rejected"]
    note: str = Field(default="", max_length=1000)


@app.post("/api/claims/{claim_id}/decision")
def claims_decide(request: Request, claim_id: str, body: DecisionIn):
    _claim_for(request, claim_id, "insurer")
    return db.update(CLAIMS, claim_id, {"status": body.status, "insurer_note": body.note})
