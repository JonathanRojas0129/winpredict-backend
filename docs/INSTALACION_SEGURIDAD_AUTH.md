# Instalación — capas de seguridad en autenticación

## 1. Dependencias Python

```bash
cd backend
pip install -r requirements.txt
```

Nueva librería requerida:

```bash
pip install slowapi==0.1.9
```

(`slowapi` ya está en `requirements.txt`)

## 2. Variables de entorno

En `backend/.env` agrega emails de administrador (separados por coma):

```env
ADMIN_EMAILS=admin@tuempresa.com,otro@tuempresa.com
```

Solo esos usuarios (autenticados con JWT) pueden llamar `POST /api/admin/desbloquear-cuenta`.

## 3. Migraciones de base de datos

**Opción A — Alembic (recomendado):**

```bash
cd backend
alembic upgrade head
```

**Opción B — SQL manual en Supabase:**

1. `migrations/sql/001_users_lockout.sql` — campos `failed_login_attempts`, `locked_until`
2. `migrations/sql/002_auth_logs.sql` — tabla `auth_logs`

## 4. Reiniciar el servidor

```bash
uvicorn app.main:app --reload --port 8000
```

## Resumen de límites (rate limiting)

| Endpoint | Límite |
|----------|--------|
| `POST /api/auth/login` | 5 / minuto / IP |
| `POST /api/auth/forgot-password` | 3 / 15 min / IP |
| `POST /api/auth/registro` | 3 / hora / IP |
| `POST /api/auth/reset-password` | 3 / 15 min / IP |

Respuesta al exceder: **HTTP 429** con mensaje en español.
