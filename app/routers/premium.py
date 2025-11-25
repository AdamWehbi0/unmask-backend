from fastapi import APIRouter, HTTPException, Depends, Body
from app.auth import verify_token
from supabase_client import get_supabase_client
from datetime import datetime, timedelta
from pydantic import BaseModel

class SubscriptionRequest(BaseModel):
	plan: str

router = APIRouter(prefix="/premium", tags=["premium"])

@router.post("/super-like/{target_user_id}")
async def super_like(
	target_user_id: str,
	user_id: str = Depends(verify_token)
):
	if user_id == target_user_id:
		raise HTTPException(status_code=400, detail="Cannot super-like yourself")
	
	client = get_supabase_client()
	
	try:
		sub = client.table("user_subscriptions").select("super_likes_remaining, plan").eq("user_id", user_id).single().execute()
		if not sub.data or sub.data["plan"] == "free":
			raise HTTPException(status_code=403, detail="Premium subscription required")
		
		if sub.data["super_likes_remaining"] <= 0:
			raise HTTPException(status_code=400, detail="No super-likes remaining")
		
		target = client.table("users").select("id").eq("id", target_user_id).is_("deleted_at", None).single().execute()
		if not target.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		client.table("user_actions").insert({
			"user_id": user_id,
			"action_type": "like",
			"target_user_id": target_user_id,
			"status": "completed"
		}).execute()
		
		client.table("user_subscriptions").update({
			"super_likes_remaining": sub.data["super_likes_remaining"] - 1,
			"updated_at": datetime.utcnow().isoformat()
		}).eq("user_id", user_id).execute()
		
		from app.services.notification_service import notify_super_like
		import asyncio
		asyncio.create_task(notify_super_like(target_user_id, user_id))
		
		mutual_like = client.table("user_actions").select("id").eq("user_id", target_user_id).eq("target_user_id", user_id).eq("action_type", "like").is_("deleted_at", None).single().execute()
		
		if mutual_like.data:
			import uuid
			match_id = str(uuid.uuid4())
			client.table("matches").insert({
				"id": match_id,
				"user1": min(user_id, target_user_id),
				"user2": max(user_id, target_user_id),
				"compatibility_score": 0.0
			}).execute()
			return {"status": "super_liked", "mutual_match": True, "match_id": match_id}
		
		return {"status": "super_liked", "mutual_match": False}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/boost")
async def boost_profile(
	user_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		sub = client.table("user_subscriptions").select("boosts_remaining, plan").eq("user_id", user_id).single().execute()
		if not sub.data or sub.data["plan"] == "free":
			raise HTTPException(status_code=403, detail="Premium subscription required")
		
		if sub.data["boosts_remaining"] <= 0:
			raise HTTPException(status_code=400, detail="No boosts remaining")
		
		boost_expires = datetime.utcnow() + timedelta(hours=24)
		
		client.table("user_subscriptions").update({
			"boosts_remaining": sub.data["boosts_remaining"] - 1,
			"boost_expires_at": boost_expires.isoformat(),
			"updated_at": datetime.utcnow().isoformat()
		}).eq("user_id", user_id).execute()
		
		client.table("analytics_events").insert({
			"user_id": user_id,
			"event_type": "boost_activated",
			"event_data": {"expires_at": boost_expires.isoformat()}
		}).execute()
		
		return {"status": "boosted", "expires_at": boost_expires.isoformat()}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/rewind/{target_user_id}")
async def rewind_last_pass(
	target_user_id: str,
	user_id: str = Depends(verify_token)
):
	if user_id == target_user_id:
		raise HTTPException(status_code=400, detail="Cannot rewind on yourself")
	
	client = get_supabase_client()
	
	try:
		sub = client.table("user_subscriptions").select("rewinds_remaining, plan").eq("user_id", user_id).single().execute()
		if not sub.data or sub.data["plan"] == "free":
			raise HTTPException(status_code=403, detail="Premium subscription required")
		
		if sub.data["rewinds_remaining"] <= 0:
			raise HTTPException(status_code=400, detail="No rewinds remaining")
		
		last_pass = client.table("user_actions").select("id").eq("user_id", user_id).eq("target_user_id", target_user_id).eq("action_type", "pass").order("created_at", desc=True).limit(1).single().execute()
		
		if not last_pass.data:
			raise HTTPException(status_code=404, detail="No previous pass found")
		
		client.table("user_actions").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", last_pass.data["id"]).execute()
		
		client.table("user_subscriptions").update({
			"rewinds_remaining": sub.data["rewinds_remaining"] - 1,
			"updated_at": datetime.utcnow().isoformat()
		}).eq("user_id", user_id).execute()
		
		return {"status": "rewound"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/subscribe")
async def subscribe(
	request: SubscriptionRequest,
	user_id: str = Depends(verify_token)
):
	if request.plan not in ["premium", "vip"]:
		raise HTTPException(status_code=400, detail="Invalid plan")
	
	try:
		from app.services.stripe_service import create_checkout_session
		
		success_url = "https://unmask.app/premium/success"
		cancel_url = "https://unmask.app/premium/cancel"
		
		checkout_url = await create_checkout_session(user_id, request.plan, success_url, cancel_url)
		
		return {"checkout_url": checkout_url}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/billing-portal")
async def get_billing_portal(
	user_id: str = Depends(verify_token)
):
	try:
		from app.services.stripe_service import get_customer_portal_session
		
		return_url = "https://unmask.app/premium"
		portal_url = await get_customer_portal_session(user_id, return_url)
		
		return {"billing_portal_url": portal_url}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/subscription-status")
async def get_subscription_status(
	user_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		sub = client.table("user_subscriptions").select("*").eq("user_id", user_id).single().execute()
		
		if not sub.data:
			return {
				"plan": "free",
				"expires_at": None,
				"super_likes_remaining": 0,
				"boosts_remaining": 0,
				"rewinds_remaining": 0
			}
		
		return {
			"plan": sub.data.get("plan", "free"),
			"expires_at": sub.data.get("expires_at"),
			"super_likes_remaining": sub.data.get("super_likes_remaining", 0),
			"boosts_remaining": sub.data.get("boosts_remaining", 0),
			"rewinds_remaining": sub.data.get("rewinds_remaining", 0)
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
