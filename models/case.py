from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CaseStudy(Base):
    __tablename__ = "case_studies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # UI: Project Name
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # UI: Template
    template: Mapped[str] = mapped_column(
        String(100),
        default="product_designer",
        nullable=False,
    )

    # User raw input
    raw_note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # AI generated case (JSON string)
    generated_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # draft | completed | archived
    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        nullable=False,
    )

    # برای نسخه‌های بعدی (Regenerate)
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )