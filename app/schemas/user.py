from pydantic import BaseModel, EmailStr, Field, field_validator
import uuid

from app.core.password_policy import enforce_password_policy

class UserBase(BaseModel):
    email: EmailStr
    nombre: str

class UserCreate(UserBase):
    password: str = Field(max_length=100)

    @field_validator("password")
    @classmethod
    def validar_politica_contrasena(cls, valor: str) -> str:
        return enforce_password_policy(valor)

class UserOut(UserBase):
    id: uuid.UUID
    es_pro: bool
    avatar_url: str | None = None

    class Config:
        from_attributes = True