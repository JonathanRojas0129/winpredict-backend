# WinPredict — Backend FastAPI

## Requisitos
- Python 3.11+
- Cuenta en [Supabase](https://supabase.com) (gratis)
- Cuenta en [Stripe](https://stripe.com) (gratis para desarrollo)

---

## Paso a paso para arrancar

### 1. Clonar y entrar a la carpeta
```bash
cd winpredict/backend
```

### 2. Crear entorno virtual
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales de Supabase y Stripe
```

### 5. Crear las tablas en Supabase (PASO CLAVE)
```bash
# Generar la migración inicial
alembic revision --autogenerate -m "tablas_iniciales"

# Crear las tablas físicamente en PostgreSQL
alembic upgrade head
```

### 6. Correr el servidor
```bash
uvicorn app.main:app --reload --port 8000
```

### 7. Ver la documentación automática
- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc

---

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /api/auth/registro | Crear cuenta |
| POST | /api/auth/login | Iniciar sesión |
| GET  | /api/auth/me | Perfil del usuario |
| POST | /api/grupos/ | Crear grupo |
| POST | /api/grupos/unirse | Unirse con código |
| GET  | /api/grupos/mis-grupos | Mis grupos |
| GET  | /api/partidos/ | Listar partidos |
| POST | /api/pronosticos/ | Registrar pronóstico |
| GET  | /api/ranking/{grupo_id} | Ranking del grupo |
| POST | /api/pro/checkout | Iniciar pago PRO $2 USD |
| POST | /api/pro/webhook | Webhook Stripe (automático) |
| GET  | /api/pro/sugerencias/{partido_id} | Sugerencia IA (solo PRO) |

---

## Estructura del proyecto
```
backend/
├── app/
│   ├── core/
│   │   ├── config.py       ← variables de entorno
│   │   ├── database.py     ← conexión PostgreSQL
│   │   └── security.py     ← JWT + hash passwords
│   ├── models/
│   │   └── models.py       ← 7 tablas SQLAlchemy
│   └── routers/
│       ├── auth.py         ← registro y login
│       ├── grupos.py       ← crear y unirse a grupos
│       ├── partidos.py     ← fixture del Mundial
│       ├── pronosticos.py  ← pronósticos + puntuación
│       ├── ranking.py      ← ranking en tiempo real
│       └── pro.py          ← Stripe $2 USD + IA
├── alembic/
│   ├── env.py              ← config de migraciones
│   └── versions/           ← historial de migraciones
├── alembic.ini
├── requirements.txt
└── .env.example
```
