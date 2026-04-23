from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import auth, grupos, partidos, pronosticos, ranking, pro, sugerencias

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de WinPredict — Polla deportiva inteligente para el Mundial 2026",
    docs_url="/docs",
    redoc_url="/redoc",
)

import logging
logging.basicConfig(level=logging.DEBUG)

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"error": str(exc)})
    
# ─── CORS ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/auth",        tags=["Auth"])
app.include_router(grupos.router,       prefix="/api/grupos",      tags=["Grupos"])
app.include_router(partidos.router,     prefix="/api/partidos",    tags=["Partidos"])
app.include_router(pronosticos.router,  prefix="/api/pronosticos", tags=["Pronósticos"])
app.include_router(ranking.router,      prefix="/api/ranking",     tags=["Ranking"])
app.include_router(pro.router,          prefix="/api/pro",         tags=["PRO · Pagos"])
app.include_router(sugerencias.router, prefix="/api/sugerencias", tags=["Sugerencias IA"])


# ─── Health check ────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ok 🟣",
    }
