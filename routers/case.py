import json
import os
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from models.case import CaseExportPreview, CaseImage
from sqlalchemy.orm import Session

from database import get_db
from repositories import (
    get_cases,
    get_case_by_id,
    update_case_content,
    update_case,

    get_case_images as repo_get_case_images,
    get_case_image as repo_get_case_image,
    create_case_image as repo_create_case_image,
    update_case_image as repo_update_case_image,
    delete_case_image as repo_delete_case_image,
    get_case_export_preview as repo_get_case_export_preview,
    create_case_export_preview as repo_create_case_export_preview,
    update_case_export_preview as repo_update_case_export_preview,
)
    
from schemas import (
    CreateCaseRequest,
    CaseListItem,
    CaseDetailResponse,
    UpdateCaseRequest,
)
from services.ai.case_builder import generate_case
from services.ai.case_editor import evaluate_field_status, CaseEditorError
from services.case_status import calculate_case_status
from services.export import (
    build_case_docx,
    build_default_preview,
    build_sections,
    image_to_dict,
    normalize_preview,
)
from services.export.common import safe_filename
from services.storage.case_storage import save_case

case_router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
)

CASE_IMAGE_UPLOAD_DIR = Path(
    os.getenv("CASE_IMAGE_UPLOAD_DIR", "uploads/case_images")
).resolve()

IMAGE_LIMITS = {
    ".png": 8 * 1024 * 1024,
    ".jpg": 8 * 1024 * 1024,
    ".jpeg": 8 * 1024 * 1024,
    ".webp": 8 * 1024 * 1024,
    ".svg": 2 * 1024 * 1024,
}

IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def _case_image_directory(case_id: int) -> Path:
    directory = (CASE_IMAGE_UPLOAD_DIR / str(case_id)).resolve()

    if CASE_IMAGE_UPLOAD_DIR != directory and CASE_IMAGE_UPLOAD_DIR not in directory.parents:
        raise HTTPException(status_code=400, detail="Invalid image path.")

    return directory


def _case_image_path(case_id: int, stored_name: str) -> Path:
    if Path(stored_name).name != stored_name:
        raise HTTPException(status_code=400, detail="Invalid image filename.")

    directory = _case_image_directory(case_id)
    image_path = (directory / stored_name).resolve()

    if directory not in image_path.parents:
        raise HTTPException(status_code=400, detail="Invalid image path.")

    return image_path


def _validate_image_bytes(filename: str, content: bytes) -> str:
    extension = Path(filename or "").suffix.lower()

    if extension not in IMAGE_LIMITS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Use PNG, JPG, WEBP, or SVG.",
        )

    if not content:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    if len(content) > IMAGE_LIMITS[extension]:
        max_mb = IMAGE_LIMITS[extension] // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"The image is larger than the {max_mb} MB limit.",
        )

    valid_signature = False

    if extension == ".png":
        valid_signature = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif extension in {".jpg", ".jpeg"}:
        valid_signature = content.startswith(b"\xff\xd8\xff")
    elif extension == ".webp":
        valid_signature = (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )
    elif extension == ".svg":
        svg_text = content.decode("utf-8", errors="ignore").lower()
        compact_svg = svg_text.lstrip("\ufeff \t\r\n")
        valid_signature = "<svg" in compact_svg[:1000]

        unsafe_tokens = (
            "<script",
            "javascript:",
            "onload=",
            "onerror=",
            "<foreignobject",
        )
        if any(token in svg_text for token in unsafe_tokens):
            raise HTTPException(
                status_code=400,
                detail="This SVG contains unsupported active content.",
            )

    if not valid_signature:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid image.",
        )

    return extension


def _stored_filename_from_location(location: str | None) -> str | None:
    if not location:
        return None

    return Path(urlparse(location).path).name or None


def _load_export_preview(
    db: Session,
    case,
    result: dict,
    images: list[CaseImage],
):
    sections = build_sections(result)
    default_preview = build_default_preview(case, sections, images)
    preview_record = repo_get_case_export_preview(db=db, case_id=case.id)

    if preview_record is None:
        preview = normalize_preview(default_preview, default_preview, images)
        preview_record = repo_create_case_export_preview(
            db=db,
            preview=CaseExportPreview(
                case_id=case.id,
                preview_json=json.dumps(preview, ensure_ascii=False),
            ),
        )
    else:
        try:
            stored_preview = json.loads(preview_record.preview_json)
        except (TypeError, json.JSONDecodeError):
            stored_preview = {}
        preview = normalize_preview(stored_preview, default_preview, images)

    return preview_record, preview, sections

@case_router.post("")
def create_case(
    request: CreateCaseRequest,
    db: Session = Depends(get_db),
):

    result = generate_case(request.note)

    if "error" in result:
        raise HTTPException(
            status_code=500,
            detail=result["error"],
        )

    case = save_case(
        db=db,
        request=request,
        result=result,
    )

    return {
        "id": case.id,
        "title": case.title,
        "template": case.template,
        "status": case.status,
        "version": case.version,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "result": result,
    }


@case_router.get(
    "",
    response_model=list[CaseListItem],
)
def list_cases(
    db: Session = Depends(get_db),
):

    return get_cases(db)


@case_router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
):

    case = get_case_by_id(
        db=db,
        case_id=case_id,
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    return {
        "id": case.id,
        "title": case.title,
        "template": case.template,
        "status": case.status,
        "version": case.version,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "result": json.loads(case.generated_json),
    }

@case_router.patch("/{case_id}")
def review_case_field(
    case_id: int,
    request: UpdateCaseRequest,
    db: Session = Depends(get_db),
):
    case = get_case_by_id(
        db=db,
        case_id=case_id,
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    current_case = json.loads(case.generated_json)

    field_name = request.field

    if field_name not in current_case:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field: {field_name}",
        )

    existing_field = current_case[field_name]
    if not isinstance(existing_field, dict):
        raise HTTPException(
            status_code=409,
            detail="Stored case field has an invalid format.",
        )

    new_content = request.content

    try:
        evaluation = evaluate_field_status(
            full_case=current_case,
            field_name=field_name,
            field_content=new_content,
        )

    except CaseEditorError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI status check failed. Please try again.",
        )

    # -------- Update JSON --------

    current_case[field_name]["content"] = new_content
    current_case[field_name]["status"] = evaluation["status"]

    update_case_content(
        db=db,
        case=case,
        generated_json=current_case,
    )

    return {
        "success": True,
        "field": field_name,
        "content": new_content,
        "status": evaluation["status"],
    }

@case_router.post("/{case_id}/status")
def update_case_status(
    case_id: int,
    db: Session = Depends(get_db),
):
    case = get_case_by_id(
        db=db,
        case_id=case_id,
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    case_json = json.loads(case.generated_json)

    status = calculate_case_status(case_json)

    case.status = status

    update_case(
        db=db,
        case=case,
    )

    return {
    "success": True,
    "status": case.status,
    "redirect": "/archive",
    "toast": {
        "type": "success",
        "title": "Case status updated",
        "description": f'"{case.title}" is now marked as {case.status.replace("_", " ").title()}.'
    }
}
