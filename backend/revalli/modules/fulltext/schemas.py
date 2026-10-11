import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_id: uuid.UUID
    filename: str
    size: int
    pages: int
    source: str
    source_url: str
    is_main: bool
    has_text: bool
    created_at: datetime


class FilesSummary(BaseModel):
    records: int
    with_pdf: int
    without_text: int
    from_open_access: int
