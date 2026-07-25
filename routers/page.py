import json
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Form,
)
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from models.case import CaseExportPreview
from sqlalchemy.orm import Session

from database import get_db
from schemas import CreateCaseRequest
from services.ai.case_builder import generate_case
from services.storage.case_storage import save_case
from services.export import (
    SECTION_DEFINITIONS,
    TOTAL_FIELDS,
    build_default_preview,
    build_sections,
    image_to_dict,
    normalize_preview,
    width_span,
)
from repositories import (
    create_case_export_preview,
    get_case_by_id,
    get_case_export_preview,
    get_case_images,
    get_cases,
)

templates = Jinja2Templates(directory="templates")

page_router = APIRouter()


@page_router.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/home.html",
    )


@page_router.get("/cases/new")
def new_case(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/new_case.html",
    )


@page_router.post("/cases/generate")
def generate_case_page(
    request: Request,
    db: Session = Depends(get_db),
    template: str = Form("product_designer"),
    project_name: str = Form(...),
    raw_notes: str = Form(...),
):

    payload = CreateCaseRequest(
        template=template,
        project_name=project_name,
        note=raw_notes,
    )

    result = generate_case(payload.note)

    if "error" in result:
        raise HTTPException(
            status_code=500,
            detail=result["error"],
        )

    case = save_case(
        db=db,
        request=payload,
        result=result,
    )

    return RedirectResponse(
        url=f"/cases/{case.id}/edit",
        status_code=303,
    )


STATUS_ORDER = [
    "complete",
    "weak",
    "unclear",
    "missing",
]


@page_router.get("/cases/{case_id}/edit")
def edit_case(
    request: Request,
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

    result = json.loads(case.generated_json)

    counts, progress = calculate_progress(result)

    sections = build_sections(result)

    review_sections = [
        section
        for section in sections
        if section["status"] != "complete"
    ]

    return templates.TemplateResponse(
        request=request,
        name="pages/edit_case.html",
        context={
            "case": case,
            "result": result,
            "sections": sections,
            "review_sections": review_sections,
            "counts": counts,
            "progress": progress,
            "filled_sections": counts["complete"],
            "total_sections": TOTAL_FIELDS,
            "custom_navbar": "partials/edit_navbar.html",
        },
    )


def calculate_progress(result: dict) -> tuple[dict, int]:

    counts = {
        "complete": 0,
        "weak": 0,
        "unclear": 0,
        "missing": 0,
    }

    for _, _, key in SECTION_DEFINITIONS:

        field = result.get(key)

        if isinstance(field, dict):
            status = field.get("status", "missing")
        else:
            status = "missing"

        if status not in counts:
            status = "missing"

        counts[status] += 1

    progress = round(
        (counts["complete"] / TOTAL_FIELDS) * 100
    )

    return counts, progress


def humanize_datetime(dt: datetime) -> str:

    now = datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc,
        )

    diff = now - dt

    seconds = int(diff.total_seconds())

    if seconds < 60:
        return "just now"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = minutes // 60

    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = diff.days

    if days == 1:
        return "yesterday"

    if days < 7:
        return f"{days} days ago"

    return dt.strftime("%b %d, %Y")

@page_router.get("/archive")
def archive(
    request: Request,
    db: Session = Depends(get_db),
):

    cases = get_cases(db)

    archive_cases = []

    for case in cases:

        result = json.loads(case.generated_json)

        counts, progress = calculate_progress(result)

        archive_cases.append(
            {
                "id": case.id,
                "title": case.title,
                "status": case.status,
                "version": case.version,
                "template": case.template,
                "updated_at": humanize_datetime(case.updated_at),
                "created_at": case.created_at,
                "progress": progress,
                "filled_sections": counts["complete"],
            }
        )

    archive_cases.sort(
        key=lambda x: x["created_at"],
        reverse=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/archive.html",
        context={
            "cases": archive_cases,
        },
    )

@page_router.get("/cases/{case_id}/export")
def export_case(
    request: Request,
    case_id: int,
    db: Session = Depends(get_db),
):
    case = get_case_by_id(db=db, case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    result = json.loads(case.generated_json)
    counts, progress = calculate_progress(result)
    sections = build_sections(result)
    images = get_case_images(db=db, case_id=case_id)

    default_preview = build_default_preview(case, sections, images)
    preview_record = get_case_export_preview(db=db, case_id=case_id)

    if preview_record is None:
        preview = normalize_preview(default_preview, default_preview, images)
        preview_record = create_case_export_preview(
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

    all_images = [image_to_dict(image) for image in images]
    images_by_id = {image["id"]: image for image in all_images}
    images_by_section = {}
    for _, _, key in SECTION_DEFINITIONS:
        images_by_section[key] = [
            images_by_id[image_id]
            for image_id in preview["sections"][key]["image_order"]
            if image_id in images_by_id
            and images_by_id[image_id]["section_key"] == key
        ]

    issues_count = counts["weak"] + counts["unclear"] + counts["missing"]

    return templates.TemplateResponse(
        request=request,
        name="pages/export.html",
        context={
            "case": case,
            "result": result,
            "sections": sections,
            "counts": counts,
            "progress": progress,
            "issues_count": issues_count,
            "filled_sections": counts["complete"],
            "total_sections": TOTAL_FIELDS,
            "custom_navbar": "partials/export_navbar.html",
            "preview": preview,
            "default_preview": default_preview,
            "preview_version": preview_record.version,
            "images_by_section": images_by_section,
            "all_images": all_images,
            "width_span": width_span,
        },
    )
