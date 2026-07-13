import json

from sqlalchemy.orm import Session

from models import CaseStudy
from repositories import create_case


def save_case(
    db: Session,
    request,
    result: dict,
) -> CaseStudy:

    case = CaseStudy(
        title=request.project_name
        or result.get("project_overview"),

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