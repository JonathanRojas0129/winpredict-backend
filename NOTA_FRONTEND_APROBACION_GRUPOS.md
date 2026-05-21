# Frontend — cambios requeridos tras aprobación de ingreso a grupos

Actualizar **después** del deploy del backend y la migración SQL en Supabase.

## 1. `POST /api/grupos/unirse` → **202 Accepted**

**Archivo:** `frontend/components/ui/ModalUnirseGrupo.tsx`

- Axios trata 202 como éxito; no cerrar el modal como si ya fuera miembro.
- Leer `response.data.message`, `grupo_nombre`, `grupo_id`.
- Mostrar mensaje: *"Solicitud enviada. El administrador del grupo debe aprobar tu ingreso."*
- **No** llamar `onUnido()` para refrescar lista (el grupo no aparecerá en mis-grupos hasta aprobación).
- Manejar **400** con los nuevos textos:
  - `Ya tienes una solicitud pendiente para este grupo`
  - `Tu solicitud fue rechazada. Contacta al administrador del grupo.`
  - `Ya eres miembro de este grupo`

## 2. `GET /api/grupos/mis-grupos`

**Archivos:** `frontend/app/dashboard/page.tsx`, cualquier lista de grupos.

- Solo devuelve grupos con `estado_participante = aprobado`.
- No se requiere cambio de contrato si ya consumían esta lista; el comportamiento es el esperado.
- Opcional: pantalla "Mis solicitudes pendientes" (no existe endpoint aún; solo UX futura).

## 3. `GET /api/grupos/{grupo_id}`

**Archivo:** `frontend/app/grupo/[id]/page.tsx`

- Manejar **403** con mensajes:
  - `Tu solicitud de ingreso está pendiente de aprobación`
  - `Tu solicitud de ingreso fue rechazada`
- Mostrar UI amigable en lugar de error genérico.

## 4. `GET /api/grupos/preview/{codigo}`

**Archivo:** `ModalUnirseGrupo.tsx`

- Mismos **400** que en `/unirse` si el usuario ya tiene solicitud o es miembro.
- `total_participantes` cuenta solo **aprobados** (capacidad real del grupo).

## 5. Nuevos endpoints (UI admin del grupo)

Solo el **creador/admin** del grupo:

| Método | Ruta | Uso en UI |
|--------|------|-----------|
| GET | `/grupos/{grupo_id}/solicitudes` | Lista pendientes con nombre, email, fecha |
| PATCH | `/grupos/{grupo_id}/solicitudes/{participante_id}/aprobar` | Botón Aprobar |
| PATCH | `/grupos/{grupo_id}/solicitudes/{participante_id}/rechazar` | Botón Rechazar |

**Sugerencia:** sección en `grupo/[id]/page.tsx` visible si `mi_rol === 'admin'`, con badge de cantidad `total` de solicitudes.

## 6. Endpoints no modificados (revisar en QA)

- `POST /api/pronosticos` y `GET /api/ranking/{grupo_id}` no filtran por `estado_participante`.
- Usuarios **pendientes** no deberían acceder al detalle del grupo; evitar deep-links directos a pronósticos hasta aprobación.

---

Migración en producción: `backend/migrations/sql/estado_participante_grupo.sql`
