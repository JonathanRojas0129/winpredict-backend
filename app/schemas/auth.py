from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
import uuid
from typing import Optional

from app.core.password_policy import enforce_password_policy, validate_password_policy


class PasswordPolicy:
    """Validador reutilizable de política de contraseñas (registro, reset, cambio)."""

    @staticmethod
    def validate(valor: str) -> str:
        return validate_password_policy(valor)


class UserBase(BaseModel):
    email: EmailStr
    nombre: str


class UserRegister(UserBase):
    """Registro con política robusta de contraseña."""

    password: str = Field(max_length=100)

    @field_validator("password")
    @classmethod
    def validar_politica_contrasena(cls, valor: str) -> str:
        return validate_password_policy(valor)


RegisterIn = UserRegister


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=100)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(max_length=100)

    @field_validator("new_password")
    @classmethod
    def validar_nueva_contrasena(cls, valor: str) -> str:
        return validate_password_policy(valor)

    @model_validator(mode="after")
    def validar_contrasenas_distintas(self) -> "ChangePasswordIn":
        if self.current_password == self.new_password:
            raise ValueError(
                "La nueva contraseña debe ser diferente a la contraseña actual."
            )
        return self


class PasswordChangeOut(BaseModel):
    detail: str = "Contraseña actualizada correctamente."


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ForgotPasswordGoogleOut(BaseModel):
    google: bool = True
    message: str = (
        "Esta cuenta usa Google. Ingresa con el botón Continuar con Google."
    )


class ForgotPasswordLocalOut(BaseModel):
    reset_token: str


class ValidateResetTokenOut(BaseModel):
    valid: bool = True
    email: str


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(max_length=100)

    @field_validator("new_password")
    @classmethod
    def validar_politica(cls, valor: str) -> str:
        return PasswordPolicy.validate(valor)


class ResetPasswordOut(BaseModel):
    message: str = "Contraseña actualizada. Ya puedes iniciar sesión."


class AdminUnlockIn(BaseModel):
    """Desbloqueo manual de cuenta por administrador."""

    email: EmailStr


class AdminUnlockOut(BaseModel):
    detail: str = "Cuenta desbloqueada correctamente."
    email: str


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
