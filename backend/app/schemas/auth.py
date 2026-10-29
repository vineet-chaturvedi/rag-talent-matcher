"""API shapes for login and user management (Step 9)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.enums import UserRole


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["admin@company.local"])
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"     # a simple shape check; the real check is that people can log in


class UserCreate(BaseModel):
    email: str = Field(..., pattern=EMAIL_PATTERN, max_length=255, examples=["manager@company.local"])
    full_name: str = Field(..., min_length=2, max_length=200)
    role: UserRole = UserRole.RESOURCE_MANAGER
    password: str = Field(..., min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def lowercase(cls, v: str) -> str:
        return v.strip().lower()        # one person = one account, whatever the capitalisation


class UserUpdate(BaseModel):
    """Only the fields you send are changed."""
    full_name: str | None = Field(None, min_length=2, max_length=200)
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=1, max_length=200)   # an admin resetting a password


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


TokenResponse.model_rebuild()
