from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class CaseStudy(Base):
    __tablename__ = "case_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    template: Mapped[str] = mapped_column(String(100), default="product_designer", nullable=False)
    raw_note: Mapped[str] = mapped_column(Text, nullable=False)
    generated_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    images: Mapped[list[CaseImage]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )
    export_preview: Mapped[CaseExportPreview | None] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        uselist=False,
    )


class CaseImage(Base):
    __tablename__ = "case_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("case_studies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), default="Other", nullable=False)
    caption: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    case: Mapped[CaseStudy] = relationship(back_populates="images")


class CaseExportPreview(Base):
    __tablename__ = "case_export_previews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("case_studies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    preview_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    case: Mapped[CaseStudy] = relationship(back_populates="export_preview")
