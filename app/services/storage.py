"""Private Cloud Storage bucket holding the original documents of each claim."""
from functools import lru_cache

from google.cloud import storage

from app import config


@lru_cache
def _bucket() -> storage.Bucket:
    return storage.Client(project=config.PROJECT_ID).bucket(config.DOCS_BUCKET)


def save(name: str, data: bytes, mime_type: str) -> str:
    _bucket().blob(name).upload_from_string(data, content_type=mime_type)
    return name


def load(name: str) -> tuple[bytes, str]:
    blob = _bucket().blob(name)
    data = blob.download_as_bytes()
    return data, blob.content_type or "application/octet-stream"
