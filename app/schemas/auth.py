from pydantic import BaseModel, EmailStr, Field
import uuid
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    nombre: str

class RegisterIn(UserBase):
    password: str = Field(min_length=8, max_length=100)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(UserBase):
    id: uuid.UUID
    es_pro: bool
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut