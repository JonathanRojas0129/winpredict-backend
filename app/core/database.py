from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # verifica la conexión antes de usarla
    pool_size=10,             # conexiones simultáneas
    max_overflow=20,
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
