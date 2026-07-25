from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreateCaseRequest(BaseModel):
    template: str = "product_designer"
    project_name: str | None = None
    note: str


class CaseListItem(BaseModel):
    id: int
    title: str | None
    template: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseDetailResponse(BaseModel):
    id: int
    title: str | None
    template: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    result: dict


class UpdateCaseRequest(BaseModel):
    title: str | None = None
    template: str | None = None
    status: str | None = None
    result: dict[str, Any] | None = None


class CaseImageCreateRequest(BaseModel):
    section_key: str
    location: str
    name: str
    evidence_type: str = "Other"
    caption: str = ""
    sort_order: int = 0


class CaseImageUpdateRequest(BaseModel):
    section_key: str | None = None
    location: str | None = None
    name: str | None = None
    evidence_type: str | None = None
    caption: str | None = None
    sort_order: int | None = None


class CaseImageBulkUpdateItem(BaseModel):
    id: int
    section_key: str | None = None
    evidence_type: str
    caption: str = ""
    sort_order: int


class CaseImageBulkUpdateRequest(BaseModel):
    items: list[CaseImageBulkUpdateItem]


class CaseImageResponse(BaseModel):
    id: int
    section_key: str
    location: str
    name: str
    evidence_type: str
    caption: str
    sort_order: int

    class Config:
        from_attributes = True
