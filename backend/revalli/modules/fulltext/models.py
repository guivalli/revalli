import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from revalli.core.db import Base, IdMixin, TimestampMixin


class RecordFile(IdMixin, TimestampMixin, Base):
    """PDF ligado a um registro (texto completo ou material suplementar)."""

    __tablename__ = "record_files"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    # upload, zip ou open_access
    source: Mapped[str] = mapped_column(String(20), default="upload")
    source_url: Mapped[str] = mapped_column(Text, default="")
    is_main: Mapped[bool] = mapped_column(Boolean, default=True)
    # Sem texto extraível: provavelmente um PDF escaneado, que precisa de OCR
    has_text: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class FilePage(Base):
    """Texto de cada página, usado na busca e, depois, na extração com citação."""

    __tablename__ = "file_pages"

    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("record_files.id", ondelete="CASCADE"), primary_key=True
    )
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, default="")
