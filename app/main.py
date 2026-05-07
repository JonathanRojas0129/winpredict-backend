from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import traceback

from app.core.config import settings
from app.routers import auth, grupos, partidos, pronosticos, ranking, pro, sugerencias

# Configuración de Logging para depuración en desarrollo
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de WinPredict — Polla deportiva inteligente para el Mundial 2026",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Manejador Global de Excepciones ────────────────────────────────────
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Captura cualquier error no controlado y devuelve un JSON estructurado."""
    logger.error(f"Error no controlado en {request.url}: {str(exc)}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor", "detail": str(exc)}
    )

# ─── Middleware de CORS ─────────────────────────────────────────────────
# Permite la conexión segura entre el Frontend (React/Next.js) y esta API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Registro de Routers (Rutas de la API) ──────────────────────────────
# Todos los endpoints están centralizados bajo el prefijo /api
app.include_router(auth.router,         prefix="/api/auth",         tags=["Auth 🔐"])
app.include_router(grupos.router,       prefix="/api/grupos",       tags=["Grupos 🏆"])
app.include_router(partidos.router,     prefix="/api/partidos",     tags=["Partidos ⚽"])
app.include_router(pronosticos.router,  prefix="/api/pronosticos",  tags=["Pronósticos 📝"])
app.include_router(ranking.router,      prefix="/api/ranking",      tags=["Ranking 📊"])
app.include_router(pro.router,          prefix="/api/pro",          tags=["PRO · Pagos 💳"])
app.include_router(sugerencias.router, prefix="/api/sugerencias",  tags=["IA · Sugerencias 🤖"])

# ─── Health Check ───────────────────────────────────────────────────────
@app.get("/", tags=["Estado"])
def health_check():
    """Ruta simple para verificar que el backend está en línea."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online 🟣",
        "modo_debug": settings.DEBUG
    }