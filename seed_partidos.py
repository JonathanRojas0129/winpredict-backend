"""
seed_partidos.py — Carga el fixture de la fase de grupos del Mundial 2026
Correr desde: backend/
Comando: python seed_partidos.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.models import Partido, FasePartido, EstadoPartido

db = SessionLocal()

# Todos los horarios en ET (UTC-4 en junio)
# Convertimos a UTC sumando 4 horas

def et_to_utc(fecha_str, hora_str):
    """Convierte fecha y hora ET a UTC"""
    dt = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
    return dt + timedelta(hours=4)

partidos = [
    # ── GRUPO A ──────────────────────────────────────────────────────────
    {"local": "México",         "vis": "Sudáfrica",      "bl": "🇲🇽", "bv": "🇿🇦", "fecha": "2026-06-11", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Corea del Sur",  "vis": "Chequia",        "bl": "🇰🇷", "bv": "🇨🇿", "fecha": "2026-06-13", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "México",         "vis": "Corea del Sur",  "bl": "🇲🇽", "bv": "🇰🇷", "fecha": "2026-06-19", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Sudáfrica",      "vis": "Chequia",        "bl": "🇿🇦", "bv": "🇨🇿", "fecha": "2026-06-19", "hora": "18:00", "fase": FasePartido.grupos},
    {"local": "Chequia",        "vis": "México",         "bl": "🇨🇿", "bv": "🇲🇽", "fecha": "2026-06-26", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Sudáfrica",      "vis": "Corea del Sur",  "bl": "🇿🇦", "bv": "🇰🇷", "fecha": "2026-06-26", "hora": "21:00", "fase": FasePartido.grupos},

    # ── GRUPO B ──────────────────────────────────────────────────────────
    {"local": "Canadá",         "vis": "Bosnia y Herz.", "bl": "🇨🇦", "bv": "🇧🇦", "fecha": "2026-06-12", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Catar",          "vis": "Suiza",          "bl": "🇶🇦", "bv": "🇨🇭", "fecha": "2026-06-13", "hora": "18:00", "fase": FasePartido.grupos},
    {"local": "Canadá",         "vis": "Catar",          "bl": "🇨🇦", "bv": "🇶🇦", "fecha": "2026-06-20", "hora": "22:00", "fase": FasePartido.grupos},
    {"local": "Suiza",          "vis": "Bosnia y Herz.", "bl": "🇨🇭", "bv": "🇧🇦", "fecha": "2026-06-20", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Suiza",          "vis": "Canadá",         "bl": "🇨🇭", "bv": "🇨🇦", "fecha": "2026-06-26", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Bosnia y Herz.", "vis": "Catar",          "bl": "🇧🇦", "bv": "🇶🇦", "fecha": "2026-06-26", "hora": "15:00", "fase": FasePartido.grupos},

    # ── GRUPO C ──────────────────────────────────────────────────────────
    {"local": "Brasil",         "vis": "Marruecos",      "bl": "🇧🇷", "bv": "🇲🇦", "fecha": "2026-06-13", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Haití",          "vis": "Escocia",        "bl": "🇭🇹", "bv": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "fecha": "2026-06-14", "hora": "18:00", "fase": FasePartido.grupos},
    {"local": "Brasil",         "vis": "Haití",          "bl": "🇧🇷", "bv": "🇭🇹", "fecha": "2026-06-20", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Escocia",        "vis": "Marruecos",      "bl": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "bv": "🇲🇦", "fecha": "2026-06-20", "hora": "18:00", "fase": FasePartido.grupos},
    {"local": "Marruecos",      "vis": "Haití",          "bl": "🇲🇦", "bv": "🇭🇹", "fecha": "2026-06-26", "hora": "18:00", "fase": FasePartido.grupos},
    {"local": "Escocia",        "vis": "Brasil",         "bl": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "bv": "🇧🇷", "fecha": "2026-06-26", "hora": "18:00", "fase": FasePartido.grupos},

    # ── GRUPO D ──────────────────────────────────────────────────────────
    {"local": "EE.UU.",         "vis": "Paraguay",       "bl": "🇺🇸", "bv": "🇵🇾", "fecha": "2026-06-12", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Australia",      "vis": "Turquía",        "bl": "🇦🇺", "bv": "🇹🇷", "fecha": "2026-06-12", "hora": "00:00", "fase": FasePartido.grupos},
    {"local": "Turquía",        "vis": "EE.UU.",         "bl": "🇹🇷", "bv": "🇺🇸", "fecha": "2026-06-18", "hora": "18:00", "fase": FasePartido.grupos},
    {"local": "EE.UU.",         "vis": "Australia",      "bl": "🇺🇸", "bv": "🇦🇺", "fecha": "2026-06-22", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Paraguay",       "vis": "Australia",      "bl": "🇵🇾", "bv": "🇦🇺", "fecha": "2026-06-27", "hora": "22:00", "fase": FasePartido.grupos},
    {"local": "Turquía",        "vis": "Paraguay",       "bl": "🇹🇷", "bv": "🇵🇾", "fecha": "2026-06-27", "hora": "22:00", "fase": FasePartido.grupos},

    # ── GRUPO E ──────────────────────────────────────────────────────────
    {"local": "Alemania",       "vis": "Curasao",        "bl": "🇩🇪", "bv": "🇨🇼", "fecha": "2026-06-14", "hora": "13:00", "fase": FasePartido.grupos},
    {"local": "Costa de Marfil","vis": "Ecuador",        "bl": "🇨🇮", "bv": "🇪🇨", "fecha": "2026-06-14", "hora": "16:00", "fase": FasePartido.grupos},
    {"local": "Alemania",       "vis": "Costa de Marfil","bl": "🇩🇪", "bv": "🇨🇮", "fecha": "2026-06-21", "hora": "20:00", "fase": FasePartido.grupos},
    {"local": "Ecuador",        "vis": "Curasao",        "bl": "🇪🇨", "bv": "🇨🇼", "fecha": "2026-06-21", "hora": "00:00", "fase": FasePartido.grupos},
    {"local": "Ecuador",        "vis": "Alemania",       "bl": "🇪🇨", "bv": "🇩🇪", "fecha": "2026-06-27", "hora": "20:00", "fase": FasePartido.grupos},
    {"local": "Curasao",        "vis": "Costa de Marfil","bl": "🇨🇼", "bv": "🇨🇮", "fecha": "2026-06-27", "hora": "20:00", "fase": FasePartido.grupos},

    # ── GRUPO F ──────────────────────────────────────────────────────────
    {"local": "Países Bajos",   "vis": "Japón",          "bl": "🇳🇱", "bv": "🇯🇵", "fecha": "2026-06-14", "hora": "16:00", "fase": FasePartido.grupos},
    {"local": "Suecia",         "vis": "Túnez",          "bl": "🇸🇪", "bv": "🇹🇳", "fecha": "2026-06-15", "hora": "12:00", "fase": FasePartido.grupos},
    {"local": "Japón",          "vis": "Suecia",         "bl": "🇯🇵", "bv": "🇸🇪", "fecha": "2026-06-21", "hora": "19:00", "fase": FasePartido.grupos},
    {"local": "Túnez",          "vis": "Países Bajos",   "bl": "🇹🇳", "bv": "🇳🇱", "fecha": "2026-06-22", "hora": "16:00", "fase": FasePartido.grupos},
    {"local": "Túnez",          "vis": "Japón",          "bl": "🇹🇳", "bv": "🇯🇵", "fecha": "2026-06-27", "hora": "16:00", "fase": FasePartido.grupos},
    {"local": "Países Bajos",   "vis": "Suecia",         "bl": "🇳🇱", "bv": "🇸🇪", "fecha": "2026-06-27", "hora": "13:00", "fase": FasePartido.grupos},

    # ── GRUPO G ──────────────────────────────────────────────────────────
    {"local": "Bélgica",        "vis": "Egipto",         "bl": "🇧🇪", "bv": "🇪🇬", "fecha": "2026-06-15", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Irán",           "vis": "Nueva Zelanda",  "bl": "🇮🇷", "bv": "🇳🇿", "fecha": "2026-06-15", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Bélgica",        "vis": "Irán",           "bl": "🇧🇪", "bv": "🇮🇷", "fecha": "2026-06-21", "hora": "13:00", "fase": FasePartido.grupos},
    {"local": "Nueva Zelanda",  "vis": "Egipto",         "bl": "🇳🇿", "bv": "🇪🇬", "fecha": "2026-06-21", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Egipto",         "vis": "Irán",           "bl": "🇪🇬", "bv": "🇮🇷", "fecha": "2026-06-27", "hora": "22:00", "fase": FasePartido.grupos},
    {"local": "Nueva Zelanda",  "vis": "Bélgica",        "bl": "🇳🇿", "bv": "🇧🇪", "fecha": "2026-06-27", "hora": "22:00", "fase": FasePartido.grupos},

    # ── GRUPO H ──────────────────────────────────────────────────────────
    {"local": "España",         "vis": "Cabo Verde",     "bl": "🇪🇸", "bv": "🇨🇻", "fecha": "2026-06-15", "hora": "13:00", "fase": FasePartido.grupos},
    {"local": "Arabia Saudí",   "vis": "Uruguay",        "bl": "🇸🇦", "bv": "🇺🇾", "fecha": "2026-06-15", "hora": "19:00", "fase": FasePartido.grupos},
    {"local": "España",         "vis": "Arabia Saudí",   "bl": "🇪🇸", "bv": "🇸🇦", "fecha": "2026-06-22", "hora": "18:00", "fase": FasePartido.grupos},
    {"local": "Uruguay",        "vis": "Cabo Verde",     "bl": "🇺🇾", "bv": "🇨🇻", "fecha": "2026-06-22", "hora": "13:00", "fase": FasePartido.grupos},
    {"local": "Uruguay",        "vis": "España",         "bl": "🇺🇾", "bv": "🇪🇸", "fecha": "2026-06-28", "hora": "20:00", "fase": FasePartido.grupos},
    {"local": "Cabo Verde",     "vis": "Arabia Saudí",   "bl": "🇨🇻", "bv": "🇸🇦", "fecha": "2026-06-28", "hora": "20:00", "fase": FasePartido.grupos},

    # ── GRUPO I ──────────────────────────────────────────────────────────
    {"local": "Francia",        "vis": "Senegal",        "bl": "🇫🇷", "bv": "🇸🇳", "fecha": "2026-06-16", "hora": "19:00", "fase": FasePartido.grupos},
    {"local": "Irak",           "vis": "Noruega",        "bl": "🇮🇶", "bv": "🇳🇴", "fecha": "2026-06-16", "hora": "00:00", "fase": FasePartido.grupos},
    {"local": "Francia",        "vis": "Irak",           "bl": "🇫🇷", "bv": "🇮🇶", "fecha": "2026-06-22", "hora": "22:00", "fase": FasePartido.grupos},
    {"local": "Noruega",        "vis": "Senegal",        "bl": "🇳🇴", "bv": "🇸🇳", "fecha": "2026-06-22", "hora": "16:00", "fase": FasePartido.grupos},
    {"local": "Senegal",        "vis": "Irak",           "bl": "🇸🇳", "bv": "🇮🇶", "fecha": "2026-06-28", "hora": "17:00", "fase": FasePartido.grupos},
    {"local": "Noruega",        "vis": "Francia",        "bl": "🇳🇴", "bv": "🇫🇷", "fecha": "2026-06-28", "hora": "17:00", "fase": FasePartido.grupos},

    # ── GRUPO J ──────────────────────────────────────────────────────────
    {"local": "Argentina",      "vis": "Argelia",        "bl": "🇦🇷", "bv": "🇩🇿", "fecha": "2026-06-16", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Austria",        "vis": "Jordania",       "bl": "🇦🇹", "bv": "🇯🇴", "fecha": "2026-06-16", "hora": "13:00", "fase": FasePartido.grupos},
    {"local": "Argentina",      "vis": "Austria",        "bl": "🇦🇷", "bv": "🇦🇹", "fecha": "2026-06-23", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Jordania",       "vis": "Argelia",        "bl": "🇯🇴", "bv": "🇩🇿", "fecha": "2026-06-23", "hora": "13:00", "fase": FasePartido.grupos},
    {"local": "Argelia",        "vis": "Austria",        "bl": "🇩🇿", "bv": "🇦🇹", "fecha": "2026-06-28", "hora": "22:00", "fase": FasePartido.grupos},
    {"local": "Jordania",       "vis": "Argentina",      "bl": "🇯🇴", "bv": "🇦🇷", "fecha": "2026-06-28", "hora": "22:00", "fase": FasePartido.grupos},

    # ── GRUPO K ──────────────────────────────────────────────────────────
    {"local": "Portugal",       "vis": "RD Congo",       "bl": "🇵🇹", "bv": "🇨🇩", "fecha": "2026-06-17", "hora": "13:00", "fase": FasePartido.grupos},
    {"local": "Colombia",       "vis": "RD Congo",       "bl": "🇨🇴", "bv": "🇨🇩", "fecha": "2026-06-17", "hora": "19:30", "fase": FasePartido.grupos},
    {"local": "Portugal",       "vis": "Uzbekistán",     "bl": "🇵🇹", "bv": "🇺🇿", "fecha": "2026-06-24", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Colombia",       "vis": "Uzbekistán",     "bl": "🇨🇴", "bv": "🇺🇿", "fecha": "2026-06-23", "hora": "22:00", "fase": FasePartido.grupos},
    {"local": "Colombia",       "vis": "Portugal",       "bl": "🇨🇴", "bv": "🇵🇹", "fecha": "2026-06-29", "hora": "20:00", "fase": FasePartido.grupos},
    {"local": "RD Congo",       "vis": "Uzbekistán",     "bl": "🇨🇩", "bv": "🇺🇿", "fecha": "2026-06-29", "hora": "20:00", "fase": FasePartido.grupos},

    # ── GRUPO L ──────────────────────────────────────────────────────────
    {"local": "Inglaterra",     "vis": "Croacia",        "bl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "bv": "🇭🇷", "fecha": "2026-06-17", "hora": "21:00", "fase": FasePartido.grupos},
    {"local": "Ghana",          "vis": "Panamá",         "bl": "🇬🇭", "bv": "🇵🇦", "fecha": "2026-06-17", "hora": "15:00", "fase": FasePartido.grupos},
    {"local": "Inglaterra",     "vis": "Ghana",          "bl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "bv": "🇬🇭", "fecha": "2026-06-23", "hora": "19:00", "fase": FasePartido.grupos},
    {"local": "Panamá",         "vis": "Croacia",        "bl": "🇵🇦", "bv": "🇭🇷", "fecha": "2026-06-23", "hora": "16:00", "fase": FasePartido.grupos},
    {"local": "Panamá",         "vis": "Inglaterra",     "bl": "🇵🇦", "bv": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "fecha": "2026-06-29", "hora": "17:00", "fase": FasePartido.grupos},
    {"local": "Croacia",        "vis": "Ghana",          "bl": "🇭🇷", "bv": "🇬🇭", "fecha": "2026-06-29", "hora": "17:00", "fase": FasePartido.grupos},
]

print(f"Cargando {len(partidos)} partidos...")

for p in partidos:
    fecha_utc = et_to_utc(p["fecha"], p["hora"])
    cierre = fecha_utc - timedelta(minutes=5)

    partido = Partido(
        equipo_local=p["local"],
        equipo_visitante=p["vis"],
        bandera_local=p["bl"],
        bandera_visitante=p["bv"],
        fecha_hora=fecha_utc,
        fase=p["fase"],
        estado=EstadoPartido.pendiente,
        cierre_pronosticos=cierre,
    )
    db.add(partido)

db.commit()
print(f"{len(partidos)} partidos cargados exitosamente en Supabase!")
db.close()