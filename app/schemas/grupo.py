from pydantic import BaseModel, Field
from typing import Optional
import uuid

class ReglasBase(BaseModel):
    pts_marcador_exacto: int = Field(default=5, ge=0, le=10)
    pts_ganador: int = Field(default=3, ge=0, le=10)
    # ... (añadir el resto de campos de reglas que estaban en grupos.py)

class GrupoCreate(BaseModel):
    nombre: str
    max_participantes: int = 500
    reglas: ReglasBase = ReglasBase()