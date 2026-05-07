from pydantic import BaseModel, EmailStr, Field
import uuid

class UserBase(BaseModel):
    email: EmailStr
    nombre: str

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserOut(UserBase):
    id: uuid.UUID
    es_pro: bool
    avatar_url: str | None = None

    class Config:
        from_attributes = True