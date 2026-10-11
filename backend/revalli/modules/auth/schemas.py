import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PASSWORD_MIN = 10


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_admin: bool
    locale: str


class _NewAccount(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=PASSWORD_MIN, max_length=200)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name must not be blank")
        return v


class SetupIn(_NewAccount):
    email: EmailStr


class SetupStatus(BaseModel):
    needs_setup: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class InvitationIn(BaseModel):
    email: EmailStr
    project_id: uuid.UUID | None = None
    role: str | None = None


class InvitationCreated(BaseModel):
    id: uuid.UUID
    email: str
    invite_url: str
    expires_at: datetime


class InvitationInfo(BaseModel):
    email: str
    project_title: str | None
    role: str | None
    account_exists: bool


class AcceptInvitationIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, min_length=PASSWORD_MIN, max_length=200)
