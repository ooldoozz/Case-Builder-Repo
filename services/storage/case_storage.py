import json

from sqlalchemy.orm import Session

from models import CaseStudy
from repositories import create_case


def save_case(
    db: Session,
    request,
    result: dict,
) -> CaseStudy:
    overview = result.get("project_overview")
    overview_content = (
        overview.get("content")
        if isinstance(overview, dict)
        else overview
    )
    title = request.project_name or overview_content or "Untitled case study"

    case = CaseStudy(
        title=str(title)[:255],

        template=request.template,

        raw_note=request.note,

        generated_json=json.dumps(
            result,
            ensure_ascii=False,
        ),

        status="draft",
    )

    return create_case(
        db=db,
        case=case,
    )
