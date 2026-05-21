"""
Cliente Supabase Auth (service role) para sincronización opcional de contraseñas.
El login de WinPredict usa password_hash en la tabla users (JWT propio).
"""

import logging
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


def supabase_auth_configured() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY)


@lru_cache
def get_supabase_admin() -> Client:
    """Cliente con service key — solo en backend."""
    if not supabase_auth_configured():
        raise RuntimeError("Supabase Auth no está configurado en .env")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def ensure_supabase_auth_user(email: str, password: str | None = None) -> bool:
    """
    Garantiza que exista un usuario en Supabase Auth para cuentas locales.
    Retorna False si Supabase no está configurado o falla la sincronización.
    """
    if not supabase_auth_configured():
        return False
    sb = get_supabase_admin()
    normalized = email.strip().lower()

    payload: dict = {
        "email": normalized,
        "email_confirm": True,
    }
    if password:
        payload["password"] = password

    try:
        sb.auth.admin.create_user(payload)
        return True
    except Exception as exc:
        msg = str(exc).lower()
        if "already" in msg or "registered" in msg or "exists" in msg:
            return True
        logger.warning("ensure_supabase_auth_user falló para %s: %s", normalized, exc)
        return False


def get_supabase_auth_user_id_by_email(email: str) -> str | None:
    """Obtiene el UUID de Supabase Auth asociado al correo (si existe)."""
    sb = get_supabase_admin()
    normalized = email.strip().lower()
    page = 1

    while page <= 20:
        try:
            result = sb.auth.admin.list_users(page=page, per_page=200)
        except Exception:
            break

        users = getattr(result, "users", None)
        if users is None and isinstance(result, dict):
            users = result.get("users", [])
        if users is None:
            users = result if isinstance(result, list) else []

        for user in users:
            u_email = (getattr(user, "email", None) or "").lower()
            if u_email == normalized:
                return str(getattr(user, "id", None) or "")

        if len(users) < 200:
            break
        page += 1

    return None


def update_supabase_auth_password(email: str, new_password: str) -> bool:
    """
    Intenta actualizar contraseña en Supabase Auth (best-effort).
    Retorna True si se sincronizó; False si no hay config o falla (el login local sigue funcionando).
    """
    if not supabase_auth_configured():
        logger.debug("Supabase Auth omitido: variables no configuradas")
        return False

    normalized = email.strip().lower()
    try:
        auth_id = get_supabase_auth_user_id_by_email(normalized)
        if not auth_id:
            ensure_supabase_auth_user(normalized, new_password)
            auth_id = get_supabase_auth_user_id_by_email(normalized)
        if not auth_id:
            logger.warning("No se encontró usuario Supabase Auth para %s", normalized)
            return False

        sb = get_supabase_admin()
        sb.auth.admin.update_user_by_id(auth_id, {"password": new_password})
        return True
    except Exception as exc:
        logger.warning("update_supabase_auth_password falló para %s: %s", normalized, exc)
        return False


def sign_out_other_supabase_sessions(access_token: str) -> bool:
    """
    Cierra sesiones Supabase Auth en otros dispositivos (scope=others).
    Requiere el JWT de la sesión actual del usuario.
    """
    if not supabase_auth_configured() or not access_token:
        return False
    try:
        sb = get_supabase_admin()
        sb.auth.admin.sign_out(access_token, scope="others")
        return True
    except Exception as exc:
        logger.warning("sign_out_other_supabase_sessions falló: %s", exc)
        return False
