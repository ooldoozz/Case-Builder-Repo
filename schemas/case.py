from typing import Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, StringConstraints
from typing_extensions import Annotated


CaseTemplate = Literal["product_designer"]
CaseFieldName = Literal[
    "project_overview",
    "problem",
    "my_role",
    "users_context",
    "research",
    "key_ux_decisions",
    "solution",
    "impact",
    "what_i_learned",
]


class CreateCaseRequest(BaseModel):
    template: CaseTemplate = "product_designer"
    project_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000)]


class CaseListItem(BaseModel):
    id: int
    title: str | None
    template: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    field: CaseFieldName
    content: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20_000)] | None = None
