from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app import config
from app.services import ai, db

BASE = Path(__file__).parent
app = FastAPI(title=config.APP_NAME)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

# Placeholder collection; rename to the real entity once the problem statement is known.
ITEMS = "items"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOADS = {"image/png", "image/jpeg", "image/webp", "application/pdf"}


def page(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        name,
        {"app_name": config.APP_NAME, "tagline": config.APP_TAGLINE, **ctx},
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "index.html", active="home")


@app.get("/api/health")
def health():
    """Live check of both cloud dependencies, shown on the home page."""
    out = {"project": config.PROJECT_ID, "model": config.GEMINI_MODEL}
    try:
        db.list_all(ITEMS, limit=1)
        out["firestore"] = "ok"
    except Exception as e:
        out["firestore"] = f"error: {str(e)[:200]}"
    try:
        ai.generate_text("Reply with exactly: ok")
        out["gemini"] = "ok"
    except Exception as e:
        out["gemini"] = f"error: {str(e)[:200]}"
    return out


class AskIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)


@app.post("/api/ai/ask")
def ai_ask(body: AskIn):
    try:
        return {"text": ai.generate_text(body.prompt)}
    except Exception as e:
        raise HTTPException(502, f"AI request failed: {str(e)[:200]}")


@app.post("/api/ai/analyze")
async def ai_analyze(prompt: str = Form(...), file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_UPLOADS:
        raise HTTPException(415, "Upload a PNG, JPEG, WebP, or PDF file.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    try:
        return {"text": ai.analyze_file(prompt, data, file.content_type)}
    except Exception as e:
        raise HTTPException(502, f"AI request failed: {str(e)[:200]}")


class ItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=4000)


@app.get("/api/items")
def items_list():
    return db.list_all(ITEMS)


@app.post("/api/items", status_code=201)
def items_add(body: ItemIn):
    return db.add(ITEMS, body.model_dump())


@app.delete("/api/items/{item_id}", status_code=204)
def items_delete(item_id: str):
    db.delete(ITEMS, item_id)
