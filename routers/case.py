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
    CaseImageResponse,
    CaseImageUpdateRequest,
    CaseImageBulkUpdateRequest,
    CaseExportPreviewResponse,
    CaseExportPreviewUpdateRequest,
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
    request: dict,
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

    updates = request.get("result")

    if not isinstance(updates, dict) or not updates:
        raise HTTPException(
            status_code=400,
            detail="Invalid payload.",
        )

    field_name = next(iter(updates.keys()))
    field_data = updates[field_name]

    if field_name not in current_case:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field: {field_name}",
        )

    new_content = field_data.get("content")

    try:
        evaluation = evaluate_field_status(
            full_case=current_case,
            field_name=field_name,
            field_content=new_content,
        )

    except CaseEditorError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI status check failed: {exc}",
        )

    # -------- Update JSON --------

    current_case[field_name]["content"] = new_content
    current_case[field_name]["status"] = evaluation["status"]

    update_case_content(
        db=db,
        case=case,
        generated_json=current_case,
    )

    print("=" * 80)
    print("CASE ID:", case_id)
    print()

    print(json.dumps(
        {field_name: current_case[field_name]},
        indent=2,
        ensure_ascii=False,
    ))

    print()
    print("AI reasoning:", evaluation["reasoning"])
    print("=" * 80)

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

@case_router.get(
    "/{case_id}/export-preview",
    response_model=CaseExportPreviewResponse,
)
def get_export_preview(
    case_id: int,
    db: Session = Depends(get_db),
):
    case = get_case_by_id(db=db, case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    result = json.loads(case.generated_json)
    images = repo_get_case_images(db=db, case_id=case_id)
    preview_record, preview, _ = _load_export_preview(db, case, result, images)

    return {
        "case_id": case.id,
        "version": preview_record.version,
        "preview": preview,
    }


@case_router.patch(
    "/{case_id}/export-preview",
    response_model=CaseExportPreviewResponse,
)
def update_export_preview(
    case_id: int,
    request: CaseExportPreviewUpdateRequest,
    db: Session = Depends(get_db),
):
    case = get_case_by_id(db=db, case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    result = json.loads(case.generated_json)
    images = repo_get_case_images(db=db, case_id=case_id)
    preview_record, _, sections = _load_export_preview(db, case, result, images)

    if request.version is not None and request.version != preview_record.version:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "The Preview changed in another request.",
                "current_version": preview_record.version,
            },
        )

    default_preview = build_default_preview(case, sections, images)
    preview = normalize_preview(request.preview, default_preview, images)
    preview_record = repo_update_case_export_preview(
        db=db,
        preview=preview_record,
        preview_json=preview,
    )

    return {
        "case_id": case.id,
        "version": preview_record.version,
        "preview": preview,
    }


@case_router.post("/{case_id}/export/docx")
def export_case_docx(
    case_id: int,
    db: Session = Depends(get_db),
):
    case = get_case_by_id(db=db, case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    result = json.loads(case.generated_json)
    images = repo_get_case_images(db=db, case_id=case_id)
    _, preview, sections = _load_export_preview(db, case, result, images)
    image_dicts = [image_to_dict(image) for image in images]

    try:
        output = build_case_docx(
            case=case,
            sections=sections,
            all_images=image_dicts,
            preview=preview,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Word export failed: {exc}",
        ) from exc

    filename = safe_filename(case.title) + ".docx"
    return StreamingResponse(
        BytesIO(output),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                "attachment; filename*=UTF-8''" + quote(filename)
            ),
            "Cache-Control": "no-store",
        },
    )


@case_router.get(
    "/{case_id}/images",
    response_model=list[CaseImageResponse],
)
def get_case_images(
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

    return repo_get_case_images(
        db=db,
        case_id=case_id,
    )


@case_router.get(
    "/{case_id}/images/files/{stored_name}",
    include_in_schema=False,
)
def get_case_image_file(
    case_id: int,
    stored_name: str,
    db: Session = Depends(get_db),
):
    case = get_case_by_id(
        db=db,
        case_id=case_id,
    )

    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    expected_location = f"/cases/{case_id}/images/files/{stored_name}"
    case_images = repo_get_case_images(db=db, case_id=case_id)

    if not any(image.location == expected_location for image in case_images):
        raise HTTPException(status_code=404, detail="Image not found.")

    image_path = _case_image_path(case_id, stored_name)

    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found.")

    extension = image_path.suffix.lower()

    return FileResponse(
        path=image_path,
        media_type=IMAGE_MEDIA_TYPES.get(extension, "application/octet-stream"),
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@case_router.post(
    "/{case_id}/images",
    response_model=CaseImageResponse,
    status_code=201,
)
async def create_case_image(
    case_id: int,
    section_key: str = Form(...),
    evidence_type: str = Form("Other"),
    caption: str = Form(""),
    file: UploadFile = File(...),
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

    section_key = section_key.strip()

    if not section_key:
        raise HTTPException(status_code=400, detail="Section key is required.")

    existing_images = repo_get_case_images(db=db, case_id=case_id)
    section_images = [
        image for image in existing_images
        if image.section_key == section_key
    ]

    if len(section_images) >= 4:
        raise HTTPException(
            status_code=400,
            detail="This section already has the maximum of 4 images.",
        )

    try:
        content = await file.read((8 * 1024 * 1024) + 1)
    finally:
        await file.close()

    extension = _validate_image_bytes(file.filename or "", content)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    image_directory = _case_image_directory(case_id)
    image_directory.mkdir(parents=True, exist_ok=True)
    image_path = _case_image_path(case_id, stored_name)
    image_path.write_bytes(content)

    next_sort_order = max(
        (image.sort_order for image in section_images),
        default=-1,
    ) + 1

    original_name = Path(file.filename or "image").name[:255] or "image"

    image = CaseImage(
        case_id=case.id,
        section_key=section_key,
        location=f"/cases/{case_id}/images/files/{stored_name}",
        name=original_name,
        evidence_type=evidence_type.strip() or "Other",
        caption=caption,
        sort_order=next_sort_order,
    )

    try:
        return repo_create_case_image(
            db=db,
            image=image,
        )
    except Exception:
        image_path.unlink(missing_ok=True)
        raise


@case_router.patch(
    "/{case_id}/images",
    response_model=list[CaseImageResponse],
)
def update_case_images(
    case_id: int,
    request: CaseImageBulkUpdateRequest,
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

    case_images = repo_get_case_images(
        db=db,
        case_id=case_id,
    )
    images_by_id = {image.id: image for image in case_images}

    requested_ids = [item.id for item in request.items]
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate image IDs are not allowed.",
        )

    updated_images = []

    try:
        for item in request.items:
            image = images_by_id.get(item.id)

            if image is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Image {item.id} not found.",
                )

            if item.section_key is not None:
                section_key = item.section_key.strip()
                if not section_key:
                    raise HTTPException(
                        status_code=400,
                        detail="Section key cannot be empty.",
                    )
                image.section_key = section_key

            image.evidence_type = item.evidence_type.strip() or "Other"
            image.caption = item.caption
            image.sort_order = max(0, item.sort_order)

            repo_update_case_image(
                db=db,
                image=image,
                commit=False,
            )
            updated_images.append(image)

        db.commit()

        for image in updated_images:
            db.refresh(image)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return repo_get_case_images(
        db=db,
        case_id=case_id,
    )


@case_router.patch(
    "/{case_id}/images/{image_id}",
    response_model=CaseImageResponse,
)
def update_case_image(
    case_id: int,
    image_id: int,
    request: CaseImageUpdateRequest,
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

    image = repo_get_case_image(
        db=db,
        case_id=case_id,
        image_id=image_id,
    )

    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found.",
        )

    if request.section_key is not None:
        section_key = request.section_key.strip()
        if not section_key:
            raise HTTPException(status_code=400, detail="Section key cannot be empty.")
        image.section_key = section_key

    # Image locations are generated only by the upload endpoint. External links
    # cannot replace an uploaded file.
    if request.location is not None and request.location != image.location:
        raise HTTPException(
            status_code=400,
            detail="Image location cannot be changed directly.",
        )

    if request.name is not None:
        image.name = Path(request.name).name[:255] or image.name

    if request.evidence_type is not None:
        image.evidence_type = request.evidence_type.strip() or "Other"

    if request.caption is not None:
        image.caption = request.caption

    if request.sort_order is not None:
        image.sort_order = max(0, request.sort_order)

    return repo_update_case_image(
        db=db,
        image=image,
    )


@case_router.delete("/{case_id}/images/{image_id}")
def delete_case_image(
    case_id: int,
    image_id: int,
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

    image = repo_get_case_image(
        db=db,
        case_id=case_id,
        image_id=image_id,
    )

    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found.",
        )

    stored_name = _stored_filename_from_location(image.location)

    repo_delete_case_image(
        db=db,
        image=image,
    )

    if stored_name:
        _case_image_path(case_id, stored_name).unlink(missing_ok=True)

    return {
        "success": True,
    }

