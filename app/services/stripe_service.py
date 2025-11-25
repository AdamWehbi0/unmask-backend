import stripe
import logging
from datetime import datetime, timedelta
from supabase_client import get_supabase_client
from app.config import STRIPE_SECRET_KEY, STRIPE_PREMIUM_PRICE_ID, STRIPE_VIP_PRICE_ID
from app.services.analytics import log_event

logger = logging.getLogger(__name__)

stripe.api_key = STRIPE_SECRET_KEY

PLANS = {
	"premium": {
		"price_id": STRIPE_PREMIUM_PRICE_ID,
		"price_cents": 999,
		"super_likes": 5,
		"boosts": 2,
		"rewinds": 1
	},
	"vip": {
		"price_id": STRIPE_VIP_PRICE_ID,
		"price_cents": 2999,
		"super_likes": 20,
		"boosts": 10,
		"rewinds": 5
	}
}

async def create_checkout_session(user_id: str, plan: str, success_url: str, cancel_url: str) -> str:
	try:
		if plan not in PLANS:
			raise ValueError(f"Invalid plan: {plan}")
		
		client = get_supabase_client()
		
		user = client.table("users").select("email").eq("id", user_id).single().execute()
		email = user.data.get("email") if user.data else None
		
		existing_sub = client.table("user_subscriptions").select("stripe_customer_id").eq("user_id", user_id).single().execute()
		
		if existing_sub.data and existing_sub.data.get("stripe_customer_id"):
			customer_id = existing_sub.data["stripe_customer_id"]
		else:
			customer = stripe.Customer.create(
				email=email,
				metadata={"user_id": user_id}
			)
			customer_id = customer.id
		
		session = stripe.checkout.Session.create(
			customer=customer_id,
			payment_method_types=["card"],
			line_items=[
				{
					"price": PLANS[plan]["price_id"],
					"quantity": 1
				}
			],
			mode="subscription",
			success_url=success_url,
			cancel_url=cancel_url,
			metadata={"user_id": user_id, "plan": plan}
		)
		
		await log_event(user_id, "checkout_session_created", {"plan": plan, "session_id": session.id})
		
		return session.url
	except Exception as e:
		logger.error(f"Error creating checkout session for user {user_id}: {str(e)}")
		raise

async def handle_checkout_completed(session_id: str):
	try:
		session = stripe.checkout.Session.retrieve(session_id)
		
		if session.payment_status != "paid":
			logger.warning(f"Session {session_id} payment status is {session.payment_status}")
			return
		
		user_id = session.metadata.get("user_id")
		plan = session.metadata.get("plan")
		customer_id = session.customer
		subscription_id = session.subscription
		
		if not user_id or not plan:
			logger.error(f"Missing user_id or plan in session metadata: {session_id}")
			return
		
		client = get_supabase_client()
		
		expires_at = datetime.utcnow() + timedelta(days=30)
		plan_details = PLANS[plan]
		
		existing = client.table("user_subscriptions").select("id").eq("user_id", user_id).single().execute()
		
		subscription_data = {
			"plan": plan,
			"stripe_customer_id": customer_id,
			"stripe_subscription_id": subscription_id,
			"super_likes_remaining": plan_details["super_likes"],
			"boosts_remaining": plan_details["boosts"],
			"rewinds_remaining": plan_details["rewinds"],
			"expires_at": expires_at.isoformat(),
			"updated_at": datetime.utcnow().isoformat()
		}
		
		if existing.data:
			client.table("user_subscriptions").update(subscription_data).eq("user_id", user_id).execute()
		else:
			subscription_data["user_id"] = user_id
			client.table("user_subscriptions").insert(subscription_data).execute()
		
		await log_event(user_id, "subscription_activated", {
			"plan": plan,
			"stripe_subscription_id": subscription_id,
			"expires_at": expires_at.isoformat()
		})
		
		logger.info(f"Subscription activated for user {user_id} on plan {plan}")
	except Exception as e:
		logger.error(f"Error handling checkout completion for session {session_id}: {str(e)}")
		raise

async def handle_subscription_updated(subscription_id: str):
	try:
		subscription = stripe.Subscription.retrieve(subscription_id)
		
		customer_id = subscription.customer
		
		customer = stripe.Customer.retrieve(customer_id)
		user_id = customer.metadata.get("user_id")
		
		if not user_id:
			logger.warning(f"No user_id found for subscription {subscription_id}")
			return
		
		client = get_supabase_client()
		
		plan = None
		for plan_name, plan_details in PLANS.items():
			if plan_details["price_id"] in [item.price.id for item in subscription.items.data]:
				plan = plan_name
				break
		
		if not plan:
			logger.warning(f"Could not determine plan for subscription {subscription_id}")
			return
		
		expires_at = datetime.utcnow() + timedelta(days=30)
		plan_details = PLANS[plan]
		
		client.table("user_subscriptions").update({
			"plan": plan,
			"super_likes_remaining": plan_details["super_likes"],
			"boosts_remaining": plan_details["boosts"],
			"rewinds_remaining": plan_details["rewinds"],
			"expires_at": expires_at.isoformat(),
			"updated_at": datetime.utcnow().isoformat()
		}).eq("user_id", user_id).execute()
		
		await log_event(user_id, "subscription_renewed", {
			"plan": plan,
			"expires_at": expires_at.isoformat()
		})
		
		logger.info(f"Subscription renewed for user {user_id} on plan {plan}")
	except Exception as e:
		logger.error(f"Error handling subscription update for {subscription_id}: {str(e)}")
		raise

async def handle_customer_subscription_deleted(subscription_id: str):
	try:
		subscription = stripe.Subscription.retrieve(subscription_id)
		
		customer_id = subscription.customer
		customer = stripe.Customer.retrieve(customer_id)
		user_id = customer.metadata.get("user_id")
		
		if not user_id:
			logger.warning(f"No user_id found for subscription {subscription_id}")
			return
		
		client = get_supabase_client()
		
		client.table("user_subscriptions").update({
			"plan": "free",
			"stripe_subscription_id": None,
			"expires_at": None,
			"super_likes_remaining": 0,
			"boosts_remaining": 0,
			"rewinds_remaining": 0,
			"updated_at": datetime.utcnow().isoformat()
		}).eq("user_id", user_id).execute()
		
		await log_event(user_id, "subscription_cancelled", {
			"stripe_subscription_id": subscription_id
		})
		
		logger.info(f"Subscription cancelled for user {user_id}")
	except Exception as e:
		logger.error(f"Error handling subscription deletion for {subscription_id}: {str(e)}")
		raise

async def get_customer_portal_session(user_id: str, return_url: str) -> str:
	try:
		client = get_supabase_client()
		
		sub = client.table("user_subscriptions").select("stripe_customer_id").eq("user_id", user_id).single().execute()
		
		if not sub.data or not sub.data.get("stripe_customer_id"):
			raise ValueError(f"No Stripe customer found for user {user_id}")
		
		customer_id = sub.data["stripe_customer_id"]
		
		portal_session = stripe.billing_portal.Session.create(
			customer=customer_id,
			return_url=return_url
		)
		
		await log_event(user_id, "billing_portal_accessed", {})
		
		return portal_session.url
	except Exception as e:
		logger.error(f"Error creating customer portal session for user {user_id}: {str(e)}")
		raise

def verify_webhook_signature(payload: bytes, sig_header: str, webhook_secret: str) -> dict:
	try:
		event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
		return event
	except ValueError:
		logger.error("Invalid payload")
		raise ValueError("Invalid payload")
	except stripe.error.SignatureVerificationError:
		logger.error("Invalid signature")
		raise ValueError("Invalid signature")
