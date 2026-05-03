import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, get_current_user
)
from app.models.models import User, ProveedorAuth
from pydantic import BaseModel, EmailStr, Field 

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    nombre: str
    es_pro: bool
    avatar_url: str | None

    class Config:
        from_attributes = True

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ─── Endpoints ───────────────────────────────────────────────────────────

@router.post("/registro", response_model=TokenOut, status_code=201)
def registro(data: RegisterIn, db: Session = Depends(get_db)):
    """Registrar un nuevo usuario."""
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese correo",
        )
    user = User(
        nombre=data.nombre,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        proveedor_auth=ProveedorAuth.local,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenOut(access_token=token, user=UserOut.from_orm(user))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    """Iniciar sesión con email y contraseña."""
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    token = create_access_token({"sub": str(user.id)})
    return TokenOut(access_token=token, user=UserOut.from_orm(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Obtener el perfil del usuario autenticado."""
    return current_user
