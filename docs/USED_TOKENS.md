# Invalidación de tokens de recuperación (`used_tokens`)

## Implementación actual (PostgreSQL)

La tabla `used_tokens` almacena el `jti` (JWT ID) de cada token de recuperación **ya consumido**.

```bash
cd backend
alembic upgrade head
```

Estructura:

| Columna     | Descripción                          |
|------------|--------------------------------------|
| `jti`      | PK — identificador único del JWT     |
| `used_at`  | Momento en que se usó                |
| `expires_at` | Referencia para limpieza (~15 min) |

Flujo:

1. `POST /api/auth/forgot-password` genera JWT con `jti` nuevo.
2. `GET /api/auth/validate-reset-token` rechaza si el `jti` está en `used_tokens`.
3. `POST /api/auth/reset-password` inserta el `jti` tras actualizar la contraseña.

## Alternativa con Redis (opcional)

Si prefieres Redis en lugar de la tabla:

```python
# Ejemplo conceptual
redis.setex(f"reset:jti:{jti}", 900, "1")  # TTL 15 minutos

# Al validar:
if redis.exists(f"reset:jti:{jti}"):
    raise HTTPException(401, "Token ya utilizado")

# Al consumir:
redis.setex(f"reset:jti:{jti}", 900, "1")
```

Variables sugeridas: `REDIS_URL=redis://localhost:6379/0`

No es necesario Redis si ejecutaste la migración `c4f8a2b1d905_used_tokens_table`.

## Limpieza periódica

Puedes borrar filas antiguas con un job:

```sql
DELETE FROM used_tokens WHERE expires_at < NOW();
```
