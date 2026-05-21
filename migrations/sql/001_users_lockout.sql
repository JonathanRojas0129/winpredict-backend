-- Bloqueo de cuenta tras intentos fallidos de login
-- Ejecutar en Supabase SQL Editor si no usas Alembic

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP WITHOUT TIME ZONE NULL;
