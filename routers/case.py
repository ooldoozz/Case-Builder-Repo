import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories import get_cases, get_case_by_id, update_case_content, update_case
from schemas import (
    CreateCaseRequest,
    CaseListItem,
    CaseDetailResponse,
    UpdateCaseRequest,
)
from services.ai.case_builder import generate_case
from services.ai.case_editor import evaluate_field_status, CaseEditorError
from services.case_status import calculate_case_status
from services.storage.case_storage import save_case

case_router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
)

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
