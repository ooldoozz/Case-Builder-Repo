import json

from sqlalchemy.orm import Session

from models.case import CaseExportPreview, CaseImage, CaseStudy


def create_case(db: Session, case: CaseStudy) -> CaseStudy:
    db.add(case)

    try:
        db.commit()
        db.refresh(case)
    except Exception:
        db.rollback()
        raise

    return case

def get_cases(
    db: Session,
) -> list[CaseStudy]:

    return (
        db.query(CaseStudy)
        .order_by(CaseStudy.created_at.desc())
        .all()
    )

def get_case_by_id(
    db: Session,
    case_id: int,
) -> CaseStudy | None:

    return (
        db.query(CaseStudy)
        .filter(CaseStudy.id == case_id)
        .first()
    )

def update_case(
    db: Session,
    case: CaseStudy,
) -> CaseStudy:

    try:
        db.commit()
        db.refresh(case)
    except Exception:
        db.rollback()
        raise

    return case


def get_cases(db: Session) -> list[CaseStudy]:
    return db.query(CaseStudy).order_by(CaseStudy.created_at.desc()).all()


def get_case_by_id(db: Session, case_id: int) -> CaseStudy | None:
    return db.query(CaseStudy).filter(CaseStudy.id == case_id).first()


def update_case(db: Session, case: CaseStudy) -> CaseStudy:
    db.commit()
    db.refresh(case)
    return case


def update_case_content(
    db: Session,
    case: CaseStudy,
    generated_json: dict,
    status: str | None = None,
) -> CaseStudy:
    case.generated_json = json.dumps(generated_json, ensure_ascii=False)
    if status is not None:
        case.status = status

    try:
        db.commit()
        db.refresh(case)
    except Exception:
        db.rollback()
        raise

    return case

def get_case_images(db: Session, case_id: int):
    return (
        db.query(CaseImage)
        .filter(CaseImage.case_id == case_id)
        .order_by(
            CaseImage.section_key.asc(),
            CaseImage.sort_order.asc(),
            CaseImage.id.asc(),
        )
        .all()
    )


def get_case_image(db: Session, case_id: int, image_id: int):
    return (
        db.query(CaseImage)
        .filter(CaseImage.case_id == case_id, CaseImage.id == image_id)
        .first()
    )


def create_case_image(db: Session, image: CaseImage):
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def update_case_image(db: Session, image: CaseImage, commit: bool = True):
    db.add(image)
    if commit:
        db.commit()
        db.refresh(image)
    else:
        db.flush()
    return image


def delete_case_image(db: Session, image: CaseImage):
    db.delete(image)
    db.commit()


def get_case_export_preview(db: Session, case_id: int) -> CaseExportPreview | None:
    return (
        db.query(CaseExportPreview)
        .filter(CaseExportPreview.case_id == case_id)
        .first()
    )


def create_case_export_preview(
    db: Session,
    preview: CaseExportPreview,
) -> CaseExportPreview:
    db.add(preview)
    db.commit()
    db.refresh(preview)
    return preview


def update_case_export_preview(
    db: Session,
    preview: CaseExportPreview,
    preview_json: dict,
) -> CaseExportPreview:
    preview.preview_json = json.dumps(preview_json, ensure_ascii=False)
    preview.version += 1
    db.commit()
    db.refresh(preview)
    return preview