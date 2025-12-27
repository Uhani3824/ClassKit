from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from app.models.postgresql import UserRole

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: UserRole

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_picture_url: Optional[str] = None

class User(UserBase):
    id: int
    role: UserRole
    profile_picture_url: Optional[str] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None
