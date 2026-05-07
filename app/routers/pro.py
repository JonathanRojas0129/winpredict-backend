"""
routers/pro.py — Pago PRO via MercadoPago (Checkout Pro · Colombia COP)
Flujo: POST /checkout → preference MP → frontend redirige → webhook → activa PRO
       GET /payment-status → fallback si el webhook no llega
"""
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
import mercadopago

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.models import User, Pago, EstadoPago

router = APIRouter()

# ─── Cliente MercadoPago ──────────────────────────────────────────────────
sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)


# ─── POST /checkout ───────────────────────────────────────────────────────

@router.post("/checkout")
def crear_checkout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea la preferencia de pago en MP (13,100 COP)."""
    if current_user.es_pro:
        raise HTTPException(status_code=400, detail="Ya eres usuario PRO")

    preference_data = {
        "items": [
            {
                "title":       "WinPredict PRO",
                "description": "Acceso a sugerencias IA y edición de pronósticos",
                "currency_id": "COP",
                "quantity":    1,
                "unit_price":  settings.PRO_PRICE_COP,
            }
        ],
        "payer": {"email": current_user.email},
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/pro/success",
            "failure": f"{settings.FRONTEND_URL}/pro?error=1",
            "pending": f"{settings.FRONTEND_URL}/pro?pending=1",
        },
        "auto_return":          "approved",
        "external_reference":   str(current_user.id),
        "notification_url":     f"{settings.BACKEND_URL}/api/pro/webhook",
        "statement_descriptor": "WINPREDICT",
        "payment_methods":      {"installments": 1},
    }

    pref_response = sdk.preference().create(preference_data)
    preference    = pref_response["response"]

    if pref_response["status"] not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Error con MercadoPago: {preference}")

    nuevo_pago = Pago(
        user_id=       current_user.id,
        preference_id= preference["id"],
        monto_cop=     settings.PRO_PRICE_COP,
        estado=        EstadoPago.pending,
    )
    db.add(nuevo_pago)
    db.commit()

    return {
        "checkout_url":  preference["sandbox_init_point"] if settings.DEBUG else preference["init_point"],
        "preference_id": preference["id"],
    }


# ─── GET /payment-status — Fallback del webhook ───────────────────────────

@router.get("/payment-status")
def verificar_pago(
    payment_id: str = Query(..., description="payment_id que MP adjunta en el redirect de success"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fallback: verifica el pago directamente en MP si el webhook no llegó."""
    if current_user.es_pro:
        return {"status": "approved", "ya_era_pro": True, "message": "Tu cuenta PRO ya está activa"}

    payment_response = sdk.payment().get(payment_id)
    if payment_response["status"] != 200:
        raise HTTPException(status_code=502, detail="No se pudo consultar el pago en MercadoPago.")

    payment       = payment_response["response"]
    status_pago   = payment.get("status")
    preference_id = payment.get("preference_id")
    external_ref  = payment.get("external_reference")

    if external_ref != str(current_user.id):
        raise HTTPException(status_code=403, detail="Este pago no corresponde a tu cuenta.")

    if status_pago == "approved":
        if not current_user.es_pro:
            current_user.es_pro            = True
            current_user.pro_activado_en   = datetime.utcnow()
            current_user.pro_expira_en     = datetime(2026, 7, 19, 23, 59, 59)
            current_user.stripe_payment_id = str(payment_id)

        pago = db.query(Pago).filter(Pago.preference_id == preference_id).first()
        if pago and pago.estado != EstadoPago.completado:
            pago.estado    = EstadoPago.completado
            pago.pagado_en = datetime.utcnow()

        db.commit()
        return {"status": "approved", "ya_era_pro": False, "message": "¡Pago aprobado! Tu cuenta PRO ha sido activada."}

    elif status_pago == "pending":
        return {"status": "pending", "message": "Tu pago está en proceso."}

    else:
        return {"status": status_pago, "message": "El pago fue rechazado o cancelado."}


# ─── POST /webhook — Notificación IPN de MercadoPago ─────────────────────

@router.post("/webhook")
async def mp_webhook(request: Request, db: Session = Depends(get_db)):
    """Recibe la notificación IPN de MP y activa el PRO si el pago fue aprobado."""

    if hasattr(settings, "MP_WEBHOOK_SECRET") and settings.MP_WEBHOOK_SECRET:
        x_signature  = request.headers.get("x-signature", "")
        x_request_id = request.headers.get("x-request-id", "")
        data_id      = request.query_params.get("data.id", "")

        ts = v1 = ""
        for part in x_signature.split(","):
            part = part.strip()
            if part.startswith("ts="):  ts = part[3:]
            elif part.startswith("v1="): v1 = part[3:]

        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        expected = hmac.new(
            settings.MP_WEBHOOK_SECRET.encode(),
            msg=manifest.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, v1):
            raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    tipo = body.get("type") or body.get("topic")
    if tipo != "payment":
        return {"status": "ignored"}

    payment_id = body.get("data", {}).get("id") or body.get("id")
    if not payment_id:
        return {"status": "ignored"}

    payment_response = sdk.payment().get(payment_id)
    if payment_response["status"] != 200:
        return {"status": "error", "detail": "No se pudo consultar el pago en MP"}

    payment       = payment_response["response"]
    status_pago   = payment.get("status")
    preference_id = payment.get("preference_id")
    user_id       = payment.get("external_reference")

    if status_pago != "approved" or not user_id:
        return {"status": "not_approved"}

    user = db.query(User).filter(User.id == user_id).first()
    if user and not user.es_pro:
        user.es_pro            = True
        user.pro_activado_en   = datetime.utcnow()
        user.pro_expira_en     = datetime(2026, 7, 19, 23, 59, 59)
        user.stripe_payment_id = str(payment_id)

    pago = db.query(Pago).filter(Pago.preference_id == preference_id).first()
    if pago:
        pago.estado    = EstadoPago.completado
        pago.pagado_en = datetime.utcnow()

    db.commit()
    return {"status": "ok"}