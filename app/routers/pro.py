"""
routers/pro.py — Pago PRO via MercadoPago (Checkout Pro · Colombia COP)
Flujo: POST /checkout → preference MP → frontend redirige → IPN webhook → activa PRO
"""
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.models import User, Pago, EstadoPago, SugerenciaIA
import mercadopago

router = APIRouter()

# ─── Cliente MercadoPago ─────────────────────────────────────────────────
sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)


# ─── Checkout ────────────────────────────────────────────────────────────

@router.post("/checkout")
def crear_checkout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea una preferencia de pago en MercadoPago para activar WinPredict PRO.
    Devuelve la URL de Checkout Pro para redirigir al usuario.
    """
    if current_user.es_pro:
        raise HTTPException(
            status_code=400,
            detail="Ya tienes WinPredict PRO activo",
        )

    # ── Construir la preferencia ─────────────────────────────────────────
    # Adaptado de la referencia oficial de MP para Colombia (COP)
    preference_data = {
        # Producto que se está comprando
        "items": [
            {
                "title": "WinPredict PRO",
                "description": "Predicciones con IA para toda la polla · Mundial 2026",
                "currency_id": "COP",
                "quantity": 1,
                "unit_price": settings.PRO_PRICE_COP,   # ej: 8000.0 COP (~$2 USD)
            }
        ],

        # Datos del comprador — usamos el usuario autenticado
        "payer": {
            "name":  current_user.nombre,
            "email": current_user.email,
        },

        # URLs de retorno después del pago
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/pro/success",
            "failure": f"{settings.FRONTEND_URL}/pro?error=1",
            "pending": f"{settings.FRONTEND_URL}/pro?pending=1",
        },

        # Redirige automáticamente si el pago es aprobado
        "auto_return": "approved",

        # Referencia externa: guardamos el user_id para identificarlo en el webhook
        "external_reference": str(current_user.id),

        # URL donde MP envía la notificación IPN cuando cambia el estado del pago
        "notification_url": f"{settings.BACKEND_URL}/api/pro/webhook",

        # Nombre que aparece en el resumen del extracto bancario del comprador
        "statement_descriptor": "WINPREDICT",

        # Métodos de pago — aceptamos todo lo disponible en Colombia
        "payment_methods": {
            "installments": 1,   # pago en una sola cuota (no cuotas)
        },
    }

    # ── Crear la preferencia en MP ───────────────────────────────────────
    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]

    if preference_response["status"] not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Error al crear preferencia en MercadoPago: {preference}",
        )

    preference_id = preference["id"]

    # En desarrollo usar sandbox_init_point, en producción init_point
    checkout_url = (
        preference["sandbox_init_point"]
        if settings.DEBUG
        else preference["init_point"]
    )

    # ── Registrar pago pendiente en nuestra BD ───────────────────────────
    pago = Pago(
        user_id=current_user.id,
        stripe_session_id=preference_id,   # campo reutilizado para guardar el preference_id de MP
        monto_usd=settings.PRO_PRICE_COP,
        estado=EstadoPago.pending,
    )
    db.add(pago)
    db.commit()

    return {
        "checkout_url":  checkout_url,
        "preference_id": preference_id,
    }


# ─── Webhook / IPN MercadoPago ───────────────────────────────────────────

@router.post("/webhook")
async def mp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    MercadoPago llama a este endpoint cuando hay un cambio en el estado del pago.
    Verifica la notificación, consulta el pago en la API de MP y activa el PRO
    si el pago fue aprobado.
    """
    # ── Verificar firma HMAC (si MP_WEBHOOK_SECRET está configurado) ─────
    if settings.MP_WEBHOOK_SECRET:
        x_signature  = request.headers.get("x-signature", "")
        x_request_id = request.headers.get("x-request-id", "")
        data_id      = request.query_params.get("data.id", "")

        ts = ""
        v1 = ""
        for part in x_signature.split(","):
            part = part.strip()
            if part.startswith("ts="):
                ts = part[3:]
            elif part.startswith("v1="):
                v1 = part[3:]

        # El manifest que MP firma es: "id:{data_id};request-id:{x_request_id};ts:{ts};"
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        expected = hmac.new(
            settings.MP_WEBHOOK_SECRET.encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, v1):
            raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    # ── Leer el body de la notificación ─────────────────────────────────
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    # MP puede enviar notificaciones de distintos tipos (payment, merchant_order, etc.)
    tipo = body.get("type") or body.get("topic")

    if tipo != "payment":
        return {"status": "ignored"}

    payment_id = (
        body.get("data", {}).get("id")
        or body.get("id")
    )
    if not payment_id:
        return {"status": "ignored"}

    # ── Consultar el pago real en la API de MP ───────────────────────────
    payment_response = sdk.payment().get(payment_id)

    if payment_response["status"] != 200:
        return {"status": "error", "detail": "No se pudo consultar el pago en MP"}

    payment       = payment_response["response"]
    status_pago   = payment.get("status")           # approved | pending | rejected | cancelled
    preference_id = payment.get("preference_id")
    user_id       = payment.get("external_reference")  # lo pusimos nosotros al crear la preference

    # Solo procesamos pagos aprobados
    if status_pago != "approved" or not user_id:
        return {"status": "not_approved"}

    # ── Activar PRO en el usuario ────────────────────────────────────────
    user = db.query(User).filter(User.id == user_id).first()
    if user and not user.es_pro:
        user.es_pro            = True
        user.pro_activado_en   = datetime.utcnow()
        user.pro_expira_en     = datetime(2026, 7, 19, 23, 59, 59)
        user.stripe_payment_id = str(payment_id)    # guardamos el payment_id de MP

    # ── Marcar el pago como completado en nuestra BD ─────────────────────
    pago = db.query(Pago).filter(
        Pago.stripe_session_id == preference_id
    ).first()
    if pago:
        pago.estado    = EstadoPago.completado
        pago.pagado_en = datetime.utcnow()

    db.commit()
    return {"status": "ok"}


# ─── Sugerencias IA (solo PRO) ───────────────────────────────────────────

@router.get("/sugerencias/{partido_id}")
def sugerencia_partido(
    partido_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna la sugerencia de IA para un partido. Solo usuarios PRO."""
    if not current_user.es_pro:
        raise HTTPException(
            status_code=403,
            detail="Las sugerencias IA son exclusivas de WinPredict PRO (~$8.000 COP)",
        )

    sugerencia = db.query(SugerenciaIA).filter(
        SugerenciaIA.partido_id == partido_id
    ).first()
    if not sugerencia:
        raise HTTPException(status_code=404, detail="Sugerencia no disponible aún")

    return {
        "partido_id":      partido_id,
        "goles_local":     sugerencia.goles_local,
        "goles_visitante": sugerencia.goles_visitante,
        "confianza":       round(sugerencia.confianza * 100),   # como porcentaje
        "generado_en":     sugerencia.generado_en,
    }
