import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories import get_cases, get_case_by_id, update_case
from schemas import CreateCaseRequest, CaseListItem, CaseDetailResponse, UpdateCaseRequest, UpdateCaseRequest
from services.ai.case_builder import generate_case
from services.storage.case_storage import save_case

router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
)


@router.post("")
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


@router.get(
    "",
    response_model=list[CaseListItem],
)
def list_cases(
    db: Session = Depends(get_db),
):

    return get_cases(db)


@router.get(
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

@router.put(
    "/{case_id}",
    response_model=UpdateCaseRequest,
)
def update_case_endpoint(
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

    payload = request.model_dump(exclude_unset=True)

    changed = False

    title = payload.get("title")

    if (
        title is not None
        and isinstance(title, str)
        and title.strip()
    ):
        case.title = title.strip()
        changed = True

    template = payload.get("template")

    if (
        template is not None
        and isinstance(template, str)
        and template.strip()
    ):
        case.template = template.strip()
        changed = True

    result = payload.get("result")

    if (
        result is not None
        and isinstance(result, dict)
        and len(result) > 0
    ):
        case.generated_json = json.dumps(
            result,
            ensure_ascii=False,
        )
        changed = True

    if not changed:
        raise HTTPException(
            status_code=400,
            detail="No valid fields provided for update.",
        )

    case.version += 1

    case = update_case(
        db=db,
        case=case,
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