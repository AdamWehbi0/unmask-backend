from fastapi import APIRouter, HTTPException, Request, status
from app.services import stripe_service
from app.config import STRIPE_WEBHOOK_SECRET
import logging
import stripe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/stripe")
async def stripe_webhook(request: Request):
	try:
		payload = await request.body()
		sig_header = request.headers.get("stripe-signature")
		
		if not sig_header:
			logger.warning("Missing stripe-signature header")
			raise HTTPException(status_code=400, detail="Missing signature")
		
		if not STRIPE_WEBHOOK_SECRET:
			logger.error("STRIPE_WEBHOOK_SECRET not configured")
			raise HTTPException(status_code=500, detail="Webhook secret not configured")
		
		try:
			event = stripe_service.verify_webhook_signature(
				payload,
				sig_header,
				STRIPE_WEBHOOK_SECRET
			)
		except ValueError as e:
			logger.warning(f"Webhook signature verification failed: {str(e)}")
			raise HTTPException(status_code=400, detail="Invalid signature")
		
		event_type = event["type"]
		
		if event_type == "checkout.session.completed":
			session_id = event["data"]["object"]["id"]
			await stripe_service.handle_checkout_completed(session_id)
		
		elif event_type == "customer.subscription.updated":
			subscription_id = event["data"]["object"]["id"]
			await stripe_service.handle_subscription_updated(subscription_id)
		
		elif event_type == "customer.subscription.deleted":
			subscription_id = event["data"]["object"]["id"]
			await stripe_service.handle_customer_subscription_deleted(subscription_id)
		
		else:
			logger.info(f"Unhandled event type: {event_type}")
		
		return {"status": "success"}
	
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Unexpected error in webhook handler: {str(e)}")
		raise HTTPException(status_code=500, detail="Internal server error")
