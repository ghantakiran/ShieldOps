"""Auth request/response models."""

from enum import Enum

from pydantic import BaseModel, EmailStr


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    role: UserRole = UserRole.VIEWER


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    is_active: bool
