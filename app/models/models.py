import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Enum, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base

# ─── Enums ──────────────────────────────────────────────────────────────

class ProveedorAuth(enum.Enum):
    local  = "local"
    google = "google"

class RolGrupo(enum.Enum):
    admin        = "admin"
    player       = "player"

class EstadoPartido(enum.Enum):
    pendiente  = "pendiente"
    vivo       = "vivo"
    finalizado = "finalizado"

class FuentePronostico(enum.Enum):
    manual  = "manual"
    ia      = "ia"

class EstadoPago(enum.Enum):
    pending   = "pending"
    approved  = "approved"
    rejected  = "rejected"
    completado = "completado"

# ─── Modelos ────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    nombre        = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)
    avatar_url    = Column(String(500), nullable=True)

    # PRO
    es_pro              = Column(Boolean, default=False)
    pro_activado_en     = Column(DateTime, nullable=True)
    pro_expira_en       = Column(DateTime, nullable=True)
    stripe_payment_id   = Column(String(255), nullable=True)  # reutilizado para MP payment_id

    proveedor_auth = Column(Enum(ProveedorAuth), default=ProveedorAuth.local)
    creado_en      = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    grupos_propios  = relationship("Grupo", back_populates="creador")
    participaciones = relationship("GrupoParticipante", back_populates="usuario")
    pronosticos     = relationship("Pronostico", back_populates="usuario")
    pagos           = relationship("Pago", back_populates="usuario")


class Grupo(Base):
    __tablename__ = "grupos"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creador_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    nombre          = Column(String(100), nullable=False)
    descripcion     = Column(Text, nullable=True)
    codigo_invitacion = Column(String(10), unique=True, nullable=False, index=True)
    max_participantes = Column(Integer, default=50)
    estado          = Column(String(20), default="activo")

    # Premios
    premio_valor   = Column(Float, nullable=True)
    premio_moneda  = Column(String(10), nullable=True, default="COP")

    # Reglas de puntuación
    pts_marcador_exacto  = Column(Integer, default=5)
    pts_ganador          = Column(Integer, default=3)
    pts_empate           = Column(Integer, default=2)
    pts_gol              = Column(Integer, default=1)
    pts_prediccion_unica = Column(Integer, default=2)

    # Bonos por fase
    bono_dieciseisavos = Column(Integer, default=1)
    bono_octavos       = Column(Integer, default=2)
    bono_cuartos       = Column(Integer, default=3)
    bono_semifinales   = Column(Integer, default=4)
    bono_final         = Column(Integer, default=5)

    creado_en = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    creador       = relationship("User", back_populates="grupos_propios")
    participantes = relationship("GrupoParticipante", back_populates="grupo")
    pronosticos   = relationship("Pronostico", back_populates="grupo")


class GrupoParticipante(Base):
    __tablename__ = "grupo_participantes"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=False)
    user_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rol      = Column(Enum(RolGrupo), default=RolGrupo.player)
    total_puntos = Column(Integer, default=0)
    posicion     = Column(Integer, nullable=True)
    unido_en = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("User", back_populates="participaciones")
    grupo   = relationship("Grupo", back_populates="participantes")


class Partido(Base):
    __tablename__ = "partidos"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipo_local     = Column(String(100), nullable=False)
    equipo_visitante = Column(String(100), nullable=False)
    bandera_local    = Column(String(10), nullable=True)
    bandera_visitante = Column(String(10), nullable=True)
    fecha_hora       = Column(DateTime, nullable=False)
    fase             = Column(String(50), nullable=False)

    # Resultados reales
    goles_local      = Column(Integer, nullable=True)
    goles_visitante  = Column(Integer, nullable=True)
    clasificado_local = Column(Boolean, nullable=True)

    estado             = Column(Enum(EstadoPartido), default=EstadoPartido.pendiente)
    cierre_pronosticos = Column(DateTime, nullable=False)

    pronosticos = relationship("Pronostico", back_populates="partido")
    sugerencias = relationship("SugerenciaIA", back_populates="partido")


class Pronostico(Base):
    __tablename__ = "pronosticos"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    partido_id = Column(UUID(as_uuid=True), ForeignKey("partidos.id"), nullable=False)
    grupo_id  = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=False)

    goles_local      = Column(Integer, nullable=False)
    goles_visitante  = Column(Integer, nullable=False)

    puntos_obtenidos    = Column(Integer, nullable=True)
    fuente              = Column(Enum(FuentePronostico), default=FuentePronostico.manual)
    fue_autocompletado  = Column(Boolean, default=False)

    registrado_en = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("User", back_populates="pronosticos")
    partido = relationship("Partido", back_populates="pronosticos")
    grupo   = relationship("Grupo", back_populates="pronosticos")


class Pago(Base):
    __tablename__ = "pagos"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # MercadoPago
    preference_id = Column(String(255), nullable=True)
    payment_id    = Column(String(255), nullable=True)

    # Campos legacy (compatibilidad con código anterior)
    stripe_session_id = Column(String(255), nullable=True)

    monto_usd  = Column(Float, nullable=True)
    monto_cop  = Column(Float, default=13100.0)
    estado     = Column(Enum(EstadoPago), default=EstadoPago.pending)

    creado_en  = Column(DateTime, default=datetime.utcnow)
    pagado_en  = Column(DateTime, nullable=True)

    usuario = relationship("User", back_populates="pagos")


class SugerenciaIA(Base):
    __tablename__ = "sugerencias_ia"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partido_id = Column(UUID(as_uuid=True), ForeignKey("partidos.id"), nullable=False)

    goles_local      = Column(Integer, nullable=False)
    goles_visitante  = Column(Integer, nullable=False)
    confianza        = Column(Float, nullable=False)   # 0.0 – 1.0

    generado_en = Column(DateTime, default=datetime.utcnow)

    partido = relationship("Partido", back_populates="sugerencias")