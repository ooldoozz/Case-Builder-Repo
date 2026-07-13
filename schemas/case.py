from typing import Any
from datetime import datetime
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


class UpdateCaseRequest(BaseModel):
    title: str | None = None
    template: str | None = None
    result: dict[str, Any] | None = None