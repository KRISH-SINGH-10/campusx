"""Gemini on Vertex AI. Auth comes from Application Default Credentials:
your gcloud login locally, the service account on Cloud Run. No API key."""
import json
from functools import lru_cache

from google import genai
from google.genai import types

from app import config


@lru_cache
def _client() -> genai.Client:
    return genai.Client(
        vertexai=True, project=config.PROJECT_ID, location=config.GEMINI_LOCATION
    )


def _config(system: str | None, schema, temperature: float) -> types.GenerateContentConfig:
    kwargs = {"temperature": temperature}
    if system:
        kwargs["system_instruction"] = system
    if schema is not None:
        kwargs["response_mime_type"] = "application/json"
        kwargs["response_schema"] = schema
    return types.GenerateContentConfig(**kwargs)


def generate_text(prompt: str, system: str | None = None, temperature: float = 0.4) -> str:
    r = _client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=_config(system, None, temperature),
    )
    return (r.text or "").strip()


def generate_json(prompt: str, schema, system: str | None = None, temperature: float = 0.2):
    """schema: a pydantic model class or a JSON-schema dict. Returns parsed JSON."""
    r = _client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=_config(system, schema, temperature),
    )
    return json.loads(r.text)


def analyze_file(
    prompt: str,
    data: bytes,
    mime_type: str,
    schema=None,
    system: str | None = None,
    temperature: float = 0.2,
):
    """Send an image or PDF with a prompt. Returns text, or parsed JSON if schema is given."""
    r = _client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=mime_type), prompt],
        config=_config(system, schema, temperature),
    )
    return json.loads(r.text) if schema is not None else (r.text or "").strip()
