import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Float,
    DateTime, ForeignKey, Enum, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


# ─── Enums ──────────────────────────────────────────────────────────────

class ProveedorAuth(str, enum.Enum):
    local = "local"
    google = "google"

class EstadoGrupo(str, enum.Enum):
    activo = "activo"
    cerrado = "cerrado"

class FasePartido(str, enum.Enum):
    grupos        = "grupos"
    dieciseisavos = "dieciseisavos"
    octavos       = "octavos"
    cuartos       = "cuartos"
    semifinal     = "semifinal"
    tercer_puesto = "tercer_puesto"
    final         = "final"

class EstadoPartido(str, enum.Enum):
    pendiente = "pendiente"
    vivo = "vivo"
    finalizado = "finalizado"

class RolGrupo(str, enum.Enum):
    admin = "admin"
    player = "player"

class FuentePronostico(str, enum.Enum):
    manual = "manual"
    ia = "ia"

class EstadoPago(str, enum.Enum):
    pending = "pending"
    completado = "completado"
    fallido = "fallido"


# ─── Tabla: users ───────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    nombre           = Column(String(100), nullable=False)
    password_hash    = Column(String(255), nullable=True)   # null si usa Google
    avatar_url       = Column(String(500), nullable=True)
    es_pro           = Column(Boolean, default=False, nullable=False)
    pro_activado_en  = Column(DateTime, nullable=True)
    pro_expira_en    = Column(DateTime, nullable=True)
    stripe_payment_id = Column(String(255), nullable=True)
    proveedor_auth   = Column(Enum(ProveedorAuth), default=ProveedorAuth.local)
    creado_en        = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    grupos_creados   = relationship("Grupo", back_populates="creador")
    participaciones  = relationship("GrupoParticipante", back_populates="user")
    pronosticos      = relationship("Pronostico", back_populates="user")
    pagos            = relationship("Pago", back_populates="user")


# ─── Tabla: grupos ───────────────────────────────────────────────────────

class Grupo(Base):
    __tablename__ = "grupos"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creador_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    nombre             = Column(String(100), nullable=False)
    codigo_invitacion  = Column(String(10), unique=True, nullable=False, index=True)
    max_participantes  = Column(Integer, default=50)
    premio_valor       = Column(Float, nullable=True)
    premio_moneda      = Column(String(10), nullable=True)  # COP, USD, EUR, BRL...
    descripcion        = Column(Text, nullable=True)
    estado             = Column(Enum(EstadoGrupo), default=EstadoGrupo.activo)
    creado_en          = Column(DateTime, default=datetime.utcnow)

    # ── Reglas de puntuación configurables por el admin (1-10 pts) ──────
    pts_marcador_exacto   = Column(Integer, default=5)   # score exacto
    pts_ganador           = Column(Integer, default=3)   # ganador correcto
    pts_empate            = Column(Integer, default=2)   # empate correcto
    pts_gol               = Column(Integer, default=1)   # por cada gol coincidente
    pts_prediccion_unica  = Column(Integer, default=2)   # único en acertar ese marcador
    bono_dieciseisavos    = Column(Integer, default=1)   # clasificado fase 16
    bono_octavos          = Column(Integer, default=2)   # clasificado octavos
    bono_cuartos          = Column(Integer, default=3)   # clasificado cuartos
    bono_semifinales      = Column(Integer, default=4)   # clasificado semifinal
    bono_final            = Column(Integer, default=5)   # campeón

    # Relaciones
    creador            = relationship("User", back_populates="grupos_creados")
    participantes      = relationship("GrupoParticipante", back_populates="grupo")
    pronosticos        = relationship("Pronostico", back_populates="grupo")


# ─── Tabla: grupo_participantes (pivote N a N) ───────────────────────────

class GrupoParticipante(Base):
    __tablename__ = "grupo_participantes"
    __table_args__ = (
        UniqueConstraint("grupo_id", "user_id", name="uq_grupo_user"),
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grupo_id      = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=False)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rol           = Column(Enum(RolGrupo), default=RolGrupo.player)
    total_puntos  = Column(Integer, default=0)
    posicion      = Column(Integer, nullable=True)
    unido_en      = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    grupo         = relationship("Grupo", back_populates="participantes")
    user          = relationship("User", back_populates="participaciones")


# ─── Tabla: partidos ────────────────────────────────────────────────────

class Partido(Base):
    __tablename__ = "partidos"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipo_local        = Column(String(100), nullable=False)
    equipo_visitante    = Column(String(100), nullable=False)
    bandera_local       = Column(String(10), nullable=True)   # emoji bandera
    bandera_visitante   = Column(String(10), nullable=True)
    fecha_hora          = Column(DateTime, nullable=False)
    fase                = Column(Enum(FasePartido), default=FasePartido.grupos)
    goles_local         = Column(Integer, nullable=True)       # null hasta que termine
    goles_visitante     = Column(Integer, nullable=True)
    estado              = Column(Enum(EstadoPartido), default=EstadoPartido.pendiente)
    cierre_pronosticos  = Column(DateTime, nullable=False)     # = fecha_hora - 5 min
    clasificado_local   = Column(Boolean, nullable=True)       # para eliminación directa

    # Relaciones
    pronosticos         = relationship("Pronostico", back_populates="partido")
    sugerencia_ia       = relationship("SugerenciaIA", back_populates="partido", uselist=False)


# ─── Tabla: pronosticos ─────────────────────────────────────────────────

class Pronostico(Base):
    __tablename__ = "pronosticos"
    __table_args__ = (
        UniqueConstraint("user_id", "partido_id", "grupo_id", name="uq_pronostico"),
    )

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id            = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    partido_id         = Column(UUID(as_uuid=True), ForeignKey("partidos.id"), nullable=False)
    grupo_id           = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=False)
    goles_local        = Column(Integer, nullable=False)
    goles_visitante    = Column(Integer, nullable=False)
    puntos_obtenidos   = Column(Integer, nullable=True)        # null hasta que termine
    fue_autocompletado = Column(Boolean, default=False)
    fuente             = Column(Enum(FuentePronostico), default=FuentePronostico.manual)
    registrado_en      = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    user               = relationship("User", back_populates="pronosticos")
    partido            = relationship("Partido", back_populates="pronosticos")
    grupo              = relationship("Grupo", back_populates="pronosticos")


# ─── Tabla: sugerencias_ia ───────────────────────────────────────────────

class SugerenciaIA(Base):
    __tablename__ = "sugerencias_ia"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partido_id       = Column(UUID(as_uuid=True), ForeignKey("partidos.id"), unique=True, nullable=False)
    goles_local      = Column(Integer, nullable=False)
    goles_visitante  = Column(Integer, nullable=False)
    confianza        = Column(Float, nullable=False)            # 0.0 a 1.0
    generado_en      = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    partido          = relationship("Partido", back_populates="sugerencia_ia")


# ─── Tabla: pagos ────────────────────────────────────────────────────────

class Pago(Base):
    __tablename__ = "pagos"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id           = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    stripe_session_id = Column(String(255), nullable=False, unique=True)
    monto_usd         = Column(Float, default=2.00, nullable=False)
    estado            = Column(Enum(EstadoPago), default=EstadoPago.pending)
    pagado_en         = Column(DateTime, nullable=True)

    # Relaciones
    user              = relationship("User", back_populates="pagos")
