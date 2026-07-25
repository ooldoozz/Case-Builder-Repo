from __future__ import annotations

import base64
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import urlparse

CASE_IMAGE_UPLOAD_DIR = Path(
    os.getenv("CASE_IMAGE_UPLOAD_DIR", "uploads/case_images")
).resolve()


def safe_filename(value: str | None, fallback: str = "case-study") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip())
    return cleaned.strip("-._")[:100] or fallback


def image_file_path(case_id: int, location: str | None) -> Path | None:
    if not location:
        return None
    stored_name = Path(urlparse(location).path).name
    if not stored_name or Path(stored_name).name != stored_name:
        return None

    case_directory = (CASE_IMAGE_UPLOAD_DIR / str(case_id)).resolve()
    image_path = (case_directory / stored_name).resolve()
    if case_directory not in image_path.parents or not image_path.is_file():
        return None
    return image_path


def image_data_uri(case_id: int, location: str | None) -> str | None:
    path = image_file_path(case_id, location)
    if path is None:
        return None
    mime_type, _ = mimetypes.guess_type(path.name)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type or 'application/octet-stream'};base64,{encoded}"
