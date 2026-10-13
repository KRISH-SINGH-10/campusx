"""Thin Firestore helpers. Every document gets an `id` and a `created_at`."""
from datetime import datetime
from functools import lru_cache

from google.cloud import firestore

from app import config


@lru_cache
def _db() -> firestore.Client:
    return firestore.Client(project=config.PROJECT_ID)


def _clean(doc) -> dict:
    data = doc.to_dict() or {}
    for k, v in data.items():
        if isinstance(v, datetime):
            data[k] = v.isoformat()
    data["id"] = doc.id
    return data


def add(collection: str, data: dict) -> dict:
    ref = _db().collection(collection).document()
    ref.set({**data, "created_at": firestore.SERVER_TIMESTAMP})
    return _clean(ref.get())


def put(collection: str, doc_id: str, data: dict) -> None:
    _db().collection(collection).document(doc_id).set(
        {**data, "created_at": firestore.SERVER_TIMESTAMP}
    )


def get(collection: str, doc_id: str) -> dict | None:
    doc = _db().collection(collection).document(doc_id).get()
    return _clean(doc) if doc.exists else None


def list_all(collection: str, limit: int = 50) -> list[dict]:
    q = (
        _db()
        .collection(collection)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    return [_clean(d) for d in q.stream()]


def update(collection: str, doc_id: str, data: dict) -> dict | None:
    ref = _db().collection(collection).document(doc_id)
    if not ref.get().exists:
        return None
    ref.update(data)
    return _clean(ref.get())


def delete(collection: str, doc_id: str) -> None:
    _db().collection(collection).document(doc_id).delete()
