import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app import crud, models
from app.api import deps
from app.core.config import settings

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/create-checkout-session")
def create_checkout_session(
    price_id: str,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.FRONTEND_URL}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/dashboard",
            customer_email=current_user.email,
            client_reference_id=str(current_user.id),
        )
        return {"sessionId": checkout_session.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None), db: Session = Depends(deps.get_db)):
    try:
        event = stripe.Webhook.construct_event(
            payload=await request.body(),
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail=str(e))

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session.get('client_reference_id'))
        stripe_customer_id = session.get('customer')
        
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.stripe_customer_id = stripe_customer_id
            user.subscription_status = 'active' # Or based on the specific plan
            db.commit()

    return {"status": "success"}
