import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class PronosticoIn(BaseModel):
    partido_id: uuid.UUID
    grupo_id: uuid.UUID
    goles_local: int
    goles_visitante: int
    clasificado_local: Optional[bool] = None 

class PronosticoOut(BaseModel):
    id: uuid.UUID
    partido_id: uuid.UUID
    grupo_id: uuid.UUID
    goles_local: int
    goles_visitante: int
    puntos_obtenidos: Optional[int]
    clasificado_local: Optional[bool] = None
    fuente: str
    fue_autocompletado: bool
    registrado_en: datetime

    class Config:
        from_attributes = True