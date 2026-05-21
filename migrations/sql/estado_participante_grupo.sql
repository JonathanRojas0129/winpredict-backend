-- WinPredict: aprobación de ingreso a grupos
-- Ejecutar en Supabase SQL Editor (producción) ANTES o junto con el deploy del backend.
--
-- DEFAULT 'aprobado': participantes ya existentes no quedan bloqueados.
-- La app asigna 'pendiente' explícitamente en POST /unirse y 'aprobado' al crear grupo.

ALTER TABLE grupo_participantes
ADD COLUMN IF NOT EXISTS estado_participante VARCHAR(20) NOT NULL DEFAULT 'aprobado';
