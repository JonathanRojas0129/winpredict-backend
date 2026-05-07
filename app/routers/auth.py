import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, get_current_user
)
from app.models.models import User, ProveedorAuth

# Importamos los schemas desde la nueva ubicación
from app.schemas.auth import RegisterIn, LoginIn, TokenOut, UserOut

router = APIRouter()

# NOTA: Se eliminaron las clases RegisterIn, LoginIn, UserOut y TokenOut 
# de aquí porque ya viven en app/schemas/auth.py

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
    
    # Usamos from_attributes (o from_orm si usas Pydantic v1) 
    # para convertir el modelo de SQLAlchemy al esquema de respuesta
    return TokenOut(
        access_token=token, 
        user=UserOut.model_validate(user)
    )


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
    return TokenOut(
        access_token=token, 
        user=UserOut.model_validate(user)
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Obtener el perfil del usuario autenticado."""
    return current_user
