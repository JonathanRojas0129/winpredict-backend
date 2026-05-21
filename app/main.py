from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import traceback

from slowapi.errors import RateLimitExceeded

from app.core.config import settings, cors_origins
from app.core.limiter import limiter
from app.routers import auth, admin, grupos, partidos, pronosticos, ranking, pro, sugerencias

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de WinPredict — Polla deportiva inteligente para el Mundial 2026",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Rate limiting (slowapi) ─────────────────────────────────────────────
app.state.limiter = limiter


def _format_retry_es(seconds: int) -> str:
    if seconds >= 3600:
        horas = max(1, round(seconds / 3600))
        return f"{horas} hora(s)"
    if seconds >= 60:
        mins = max(1, round(seconds / 60))
        return f"{mins} minuto(s)"
    return f"{max(1, seconds)} segundo(s)"


async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    retry_after = int(getattr(exc, "retry_after", 0) or 60)
    tiempo = _format_retry_es(retry_after)
    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                f"Demasiados intentos. Espera {tiempo} antes de intentarlo de nuevo."
            )
        },
        headers={"Retry-After": str(retry_after)},
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# ─── Manejador global de excepciones ────────────────────────────────────
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Error no controlado en %s: %s", request.url, exc)
    traceback.print_exc()
    body: dict = {"error": "Error interno del servidor"}
    if settings.DEBUG:
        body["detail"] = str(exc)
    return JSONResponse(status_code=500, content=body)


# ─── CORS ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Auth 🔐"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin 🛡️"])
app.include_router(grupos.router, prefix="/api/grupos", tags=["Grupos 🏆"])
app.include_router(partidos.router, prefix="/api/partidos", tags=["Partidos ⚽"])
app.include_router(pronosticos.router, prefix="/api/pronosticos", tags=["Pronósticos 📝"])
app.include_router(ranking.router, prefix="/api/ranking", tags=["Ranking 📊"])
app.include_router(pro.router, prefix="/api/pro", tags=["PRO · Pagos 💳"])
app.include_router(sugerencias.router, prefix="/api/sugerencias", tags=["IA · Sugerencias 🤖"])


@app.get("/", tags=["Estado"])
def health_check():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online 🟣",
        "modo_debug": settings.DEBUG,
    }
