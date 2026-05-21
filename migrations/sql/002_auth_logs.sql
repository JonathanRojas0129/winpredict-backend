-- Auditoría de autenticación
-- Ejecutar en Supabase SQL Editor si no usas Alembic

CREATE TABLE IF NOT EXISTS auth_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  email VARCHAR(255) NOT NULL,
  accion VARCHAR(50) NOT NULL,
  ip VARCHAR(64) NOT NULL,
  user_agent VARCHAR(500) NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_auth_logs_email ON auth_logs (email);
CREATE INDEX IF NOT EXISTS ix_auth_logs_accion ON auth_logs (accion);
CREATE INDEX IF NOT EXISTS ix_auth_logs_created_at ON auth_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_auth_logs_user_id ON auth_logs (user_id);
