import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import List, Dict

class SugerenciaOut(BaseModel):
    partido_id: uuid.UUID
    goles_local: int
    goles_visitante: int
    confianza: float  # 0.0 a 100.0
    probabilidades: Dict[str, float]  # Ejemplo: {"Local": 45.2, "Empate": 20.1, "Visitante": 34.7}
    generado_en: datetime

    class Config:
        from_attributes = True