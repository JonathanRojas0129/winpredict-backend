from pydantic_settings import BaseSettings
from functools import lru_cache


def _normalize_origin(url: str) -> str:
    """CORS exige origen completo con esquema (https://dominio)."""
    u = url.strip().rstrip("/")
    if not u:
        return u
    if not u.startswith(("http://", "https://")):
        u = f"https://{u}"
    return u


class Settings(BaseSettings):
    # App
    APP_NAME: str = "WinPredict"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    # Orígenes extra para CORS, separados por coma (ej. preview de Vercel)
    CORS_EXTRA_ORIGINS: str = ""

    # Base de datos
    DATABASE_URL: str

    # Supabase Auth (recuperación de contraseña)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 días

    # Jobs internos (score_updater → calcular-puntos). En producción debe estar definida.
    INTERNAL_API_KEY: str = ""

    # Administración (emails con permiso para /api/admin/*), separados por coma
    ADMIN_EMAILS: str = ""

    # MercadoPago
    MP_ACCESS_TOKEN: str = ""
    MP_WEBHOOK_SECRET: str = ""   # se configura en el panel de MP al registrar el webhook
    PRO_PRICE_COP: float = 14500.0  # ~$3.5 USD en COP
    PRO_PRICE_USD: float = 3.5

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def cors_origins() -> list[str]:
    """Orígenes permitidos para el frontend (Vercel, Render, local)."""
    s = get_settings()
    candidates = [
        s.FRONTEND_URL,
        "http://localhost:3000",
        "https://winpredict-frontend.vercel.app",
        "https://winpredictfornt.onrender.com",
        "https://win-predict.vercel.app",
    ]
    if s.CORS_EXTRA_ORIGINS:
        candidates.extend(s.CORS_EXTRA_ORIGINS.split(","))
    seen: set[str] = set()
    out: list[str] = []
    for raw in candidates:
        origin = _normalize_origin(raw)
        if origin and origin not in seen:
            seen.add(origin)
            out.append(origin)
    return out


settings = get_settings()
