"""
routers/pro.py — Pago PRO $2 USD via Stripe
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.models import User, Pago, EstadoPago, SugerenciaIA
import stripe

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY


# ─── Checkout ────────────────────────────────────────────────────────────

@router.post("/checkout")
def crear_checkout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea una sesión de pago Stripe para activar PRO ($2 USD)."""
    if current_user.es_pro:
        raise HTTPException(status_code=400, detail="Ya tienes WinPredict PRO activo")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": 200,          # $2.00 USD en centavos
                "product_data": {
                    "name": "WinPredict PRO",
                    "description": "Predicciones IA para toda la polla · Mundial 2026",
                },
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{settings.FRONTEND_URL}/pro/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/pro",
        metadata={"user_id": str(current_user.id)},
    )

    # Registrar el pago en estado pendiente
    pago = Pago(
        user_id=current_user.id,
        stripe_session_id=session.id,
        monto_usd=2.00,
        estado=EstadoPago.pending,
    )
    db.add(pago)
    db.commit()

    return {"checkout_url": session.url, "session_id": session.id}


# ─── Webhook Stripe ──────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe llama a este endpoint cuando el pago se confirma.
    Activa el PRO automáticamente sin intervención manual.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"]["user_id"]

        # Activar PRO en el usuario
        user = db.query(User).filter(User.id == user_id).first()
        if user and not user.es_pro:
            user.es_pro = True
            user.pro_activado_en = datetime.utcnow()
            user.stripe_payment_id = session["id"]

        # Marcar el pago como completado
        pago = db.query(Pago).filter(
            Pago.stripe_session_id == session["id"]
        ).first()
        if pago:
            pago.estado = EstadoPago.completado
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
    """Retorna la sugerencia IA para un partido. Solo usuarios PRO."""
    if not current_user.es_pro:
        raise HTTPException(
            status_code=403,
            detail="Las sugerencias IA son exclusivas de WinPredict PRO ($2 USD)",
        )
    sugerencia = db.query(SugerenciaIA).filter(
        SugerenciaIA.partido_id == partido_id
    ).first()
    if not sugerencia:
        raise HTTPException(status_code=404, detail="Sugerencia no disponible aún")

    return {
        "partido_id": partido_id,
        "goles_local": sugerencia.goles_local,
        "goles_visitante": sugerencia.goles_visitante,
        "confianza": round(sugerencia.confianza * 100),   # porcentaje
        "generado_en": sugerencia.generado_en,
    }
