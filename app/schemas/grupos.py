import uuid
from pydantic import BaseModel, Field
from typing import Optional

class ReglasIn(BaseModel):
    """Reglas de puntuación configurables por el admin. Rango: 0-10 pts."""
    pts_marcador_exacto:  int = Field(default=5,  ge=0, le=10)
    pts_ganador:          int = Field(default=3,  ge=0, le=10)
    pts_empate:           int = Field(default=2,  ge=0, le=10)
    pts_gol:              int = Field(default=1,  ge=0, le=10)
    pts_prediccion_unica: int = Field(default=2,  ge=0, le=10)
    bono_dieciseisavos:   int = Field(default=1,  ge=0, le=10)
    bono_octavos:         int = Field(default=2,  ge=0, le=10)
    bono_cuartos:         int = Field(default=3,  ge=0, le=10)
    bono_semifinales:     int = Field(default=4,  ge=0, le=10)
    bono_final:           int = Field(default=5,  ge=0, le=10)

class GrupoIn(BaseModel):
    nombre:            str
    max_participantes: int = 500
    premio_valor:      Optional[float] = None
    premio_moneda:     Optional[str]  = None
    descripcion:       Optional[str]  = None
    reglas:            ReglasIn = ReglasIn()

class GrupoOut(BaseModel):
    id:                   uuid.UUID
    nombre:               str
    codigo_invitacion:    str
    max_participantes:    int
    premio_valor:         Optional[float]
    premio_moneda:        Optional[str]
    descripcion:          Optional[str]
    pts_marcador_exacto:  int
    pts_ganador:          int
    pts_empate:           int
    pts_gol:              int
    pts_prediccion_unica: int
    bono_dieciseisavos:   int
    bono_octavos:         int
    bono_cuartos:         int
    bono_semifinales:     int
    bono_final:           int
    total_participantes:  int = 0

    class Config:
        from_attributes = True

class UnirseIn(BaseModel):
    codigo_invitacion: str