import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class PartidoOut(BaseModel):
    id: uuid.UUID
    equipo_local: str
    equipo_visitante: str
    bandera_local: Optional[str]
    bandera_visitante: Optional[str]
    fecha_hora: datetime
    fase: str
    grupo: Optional[str] = None  
    goles_local: Optional[int]
    goles_visitante: Optional[int]
    estado: str
    cierre_pronosticos: datetime

    class Config:
        from_attributes = True