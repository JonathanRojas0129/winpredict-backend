from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,          # reducir de 10 a 3
    max_overflow=7,       # reducir de 20 a 7 — total 10 máximo
    pool_timeout=20,      # espera máxima antes de error
    pool_recycle=1800,    # recicla conexiones cada 30 min
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency para inyectar la sesión de BD en cada endpoint."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
