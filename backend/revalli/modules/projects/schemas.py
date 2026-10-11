import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from revalli.modules.projects.models import ReviewType, Role


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=20_000)
    review_type: ReviewType = ReviewType.systematic


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    review_type: ReviewType | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    review_type: ReviewType
    created_at: datetime
    my_role: Role | None = None
    member_count: int = 0


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: Role
    joined_at: datetime


class MemberIn(BaseModel):
    email: EmailStr
    role: Role = Role.reviewer


class MemberPatch(BaseModel):
    role: Role
