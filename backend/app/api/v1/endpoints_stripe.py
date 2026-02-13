import logging

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import crud, models
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db

logger = logging.getLogger("stock_analyzer.api.stripe")

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/create-checkout-session")
def create_checkout_session(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a Stripe checkout session for the premium subscription."""
    if not settings.STRIPE_PREMIUM_PRICE_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment processing is not configured.",
        )

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{"price": settings.STRIPE_PREMIUM_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.FRONTEND_URL}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/pricing",
            customer_email=current_user.email,
            client_reference_id=str(current_user.id),
        )
        return {"sessionId": checkout_session.id}
    except stripe.error.StripeError as e:
        logger.error("Stripe checkout error for user %d: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment processing error. Please try again.",
        )


@router.post("/cancel-subscription")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cancel the current user's Stripe subscription."""
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found.",
        )

    try:
        # List active subscriptions for this customer
        subscriptions = stripe.Subscription.list(
            customer=current_user.stripe_customer_id,
            status="active",
            limit=1,
        )
        if not subscriptions.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription found.",
            )

        # Cancel at period end (graceful cancellation)
        sub = stripe.Subscription.modify(
            subscriptions.data[0].id,
            cancel_at_period_end=True,
        )
        logger.info(
            "Subscription %s set to cancel at period end for user %d",
            sub.id, current_user.id,
        )
        return {
            "message": "Subscription will be cancelled at the end of the current billing period.",
            "cancel_at": sub.cancel_at,
        }
    except stripe.error.StripeError as e:
        logger.error("Stripe cancel error for user %d: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cancel subscription. Please try again.",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db),
):
    """Handle incoming Stripe webhook events."""
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature header.",
        )

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        logger.warning("Invalid Stripe webhook payload")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload.")
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature.")

    event_type = event["type"]
    session = event["data"]["object"]

    # ── Checkout completed: activate subscription
    if event_type == "checkout.session.completed":
        client_ref_id = session.get("client_reference_id")
        stripe_customer_id = session.get("customer")

        if client_ref_id and stripe_customer_id:
            user_id = int(client_ref_id)
            crud.update_user_subscription(
                db, user_id=user_id, stripe_customer_id=stripe_customer_id, status="active",
            )
            logger.info("Subscription activated for user %d", user_id)
        else:
            logger.warning("Webhook checkout.session.completed missing client_reference_id or customer")

    # ── Subscription deleted: deactivate
    elif event_type == "customer.subscription.deleted":
        stripe_customer_id = session.get("customer")
        if stripe_customer_id:
            user = crud.deactivate_subscription_by_stripe_id(db, stripe_customer_id)
            if user:
                logger.info("Subscription deactivated for user %d (stripe: %s)", user.id, stripe_customer_id)
            else:
                logger.warning("No user found for stripe customer %s during subscription.deleted", stripe_customer_id)

    # ── Invoice payment failed: warn
    elif event_type == "invoice.payment_failed":
        stripe_customer_id = session.get("customer")
        logger.warning("Payment failed for stripe customer %s", stripe_customer_id)

    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"status": "success"}
