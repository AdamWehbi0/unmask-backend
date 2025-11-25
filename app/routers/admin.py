from fastapi import APIRouter, HTTPException, Depends, Query
from app.auth import verify_token
from supabase_client import get_supabase_client
from datetime import datetime, timedelta

router = APIRouter(prefix="/admin", tags=["admin"])

def require_admin(user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	user = client.table("users").select("is_admin").eq("id", user_id).single().execute()
	if not user.data or not user.data.get("is_admin"):
		raise HTTPException(status_code=403, detail="Admin access required")
	return user_id

@router.get("/dashboard/stats")
async def get_dashboard_stats(admin_id: str = Depends(require_admin)):
	client = get_supabase_client()
	
	try:
		today = datetime.utcnow().date().isoformat()
		week_ago = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
		
		total_users = client.table("users").select("id").is_("deleted_at", None).execute()
		today_signups = client.table("users").select("id").gte("created_at", today).is_("deleted_at", None).execute()
		week_signups = client.table("users").select("id").gte("created_at", week_ago).is_("deleted_at", None).execute()
		
		total_matches = client.table("matches").select("id").is_("deleted_at", None).execute()
		today_matches = client.table("matches").select("id").gte("created_at", today).is_("deleted_at", None).execute()
		
		premium_users = client.table("user_subscriptions").select("id").neq("plan", "free").execute()
		
		return {
			"total_users": len(total_users.data),
			"today_signups": len(today_signups.data),
			"week_signups": len(week_signups.data),
			"total_matches": len(total_matches.data),
			"today_matches": len(today_matches.data),
			"premium_users": len(premium_users.data),
			"timestamp": datetime.utcnow().isoformat()
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/users")
async def search_users(
	admin_id: str = Depends(require_admin),
	query: str = Query(""),
	limit: int = Query(50, ge=1, le=100),
	offset: int = Query(0, ge=0)
):
	client = get_supabase_client()
	
	try:
		if query:
			users = client.table("users").select("id, email, created_at, is_verified, deleted_at").ilike("email", f"%{query}%").execute()
		else:
			users = client.table("users").select("id, email, created_at, is_verified, deleted_at").execute()
		
		paginated = users.data[offset:offset + limit]
		
		return {
			"data": paginated,
			"total": len(users.data),
			"limit": limit,
			"offset": offset
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/{user_id}/suspend")
async def suspend_user(
	user_id: str,
	admin_id: str = Depends(require_admin)
):
	client = get_supabase_client()
	
	try:
		user = client.table("users").select("id").eq("id", user_id).single().execute()
		if not user.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		client.table("users").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).eq("id", user_id).execute()
		
		client.table("audit_logs").insert({
			"admin_id": admin_id,
			"action": "suspend",
			"target_user_id": user_id,
			"details": {"timestamp": datetime.utcnow().isoformat()}
		}).execute()
		
		return {"status": "suspended"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(
	user_id: str,
	admin_id: str = Depends(require_admin)
):
	client = get_supabase_client()
	
	try:
		user = client.table("users").select("id").eq("id", user_id).single().execute()
		if not user.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		client.table("users").update({
			"deleted_at": None
		}).eq("id", user_id).execute()
		
		client.table("audit_logs").insert({
			"admin_id": admin_id,
			"action": "unsuspend",
			"target_user_id": user_id,
			"details": {"timestamp": datetime.utcnow().isoformat()}
		}).execute()
		
		return {"status": "unsuspended"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{user_id}")
async def delete_user_data(
	user_id: str,
	admin_id: str = Depends(require_admin)
):
	client = get_supabase_client()
	
	try:
		# GDPR deletion - clear PII
		client.table("users").update({
			"email": f"deleted_{user_id}@example.com",
			"bio": None,
			"traits": [],
			"values": [],
			"green_flags": [],
			"red_flags": [],
			"lifestyle": [],
			"deleted_at": datetime.utcnow().isoformat()
		}).eq("id", user_id).execute()
		
		# Clear messages
		client.table("messages").update({
			"content": "[deleted]"
		}).eq("sender_id", user_id).execute()
		
		# Soft delete from related tables
		client.table("user_interests").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).eq("user_id", user_id).execute()
		
		client.table("user_blocks").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).or_(f"blocker_id.eq.{user_id},blocked_id.eq.{user_id}").execute()
		
		client.table("abuse_reports").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).or_(f"reporter_id.eq.{user_id},reported_id.eq.{user_id}").execute()
		
		client.table("user_actions").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).or_(f"user_id.eq.{user_id},target_user_id.eq.{user_id}").execute()
		
		client.table("notification_tokens").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).eq("user_id", user_id).execute()
		
		# Log audit
		client.table("audit_logs").insert({
			"admin_id": admin_id,
			"action": "delete",
			"target_user_id": user_id,
			"details": {"type": "gdpr_delete", "timestamp": datetime.utcnow().isoformat()}
		}).execute()
		
		return {"status": "deleted"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/funnels")
async def get_analytics_funnels(admin_id: str = Depends(require_admin)):
	client = get_supabase_client()
	
	try:
		total_users = len(client.table("users").select("id").is_("deleted_at", None).execute().data)
		
		profile_complete = len(client.table("users").select("id").eq("profile_complete", True).is_("deleted_at", None).execute().data)
		
		with_interests = len(client.table("user_interests").select("user_id").execute().data)
		
		with_matches = len(client.table("matches").select("user1").is_("deleted_at", None).execute().data)
		
		with_messages = len(client.table("messages").select("sender_id").execute().data)
		
		revealed_matches = len(client.table("matches").select("id").eq("reveal_user1", True).eq("reveal_user2", True).is_("deleted_at", None).execute().data)
		
		return {
			"total_users": total_users,
			"profile_complete": profile_complete,
			"profile_complete_pct": (profile_complete / total_users * 100) if total_users > 0 else 0,
			"users_with_interests": with_interests,
			"users_with_interests_pct": (with_interests / total_users * 100) if total_users > 0 else 0,
			"users_with_matches": with_matches,
			"users_with_matches_pct": (with_matches / total_users * 100) if total_users > 0 else 0,
			"users_with_messages": with_messages,
			"users_with_messages_pct": (with_messages / total_users * 100) if total_users > 0 else 0,
			"revealed_matches": revealed_matches,
			"revealed_matches_pct": (revealed_matches / with_matches * 100) if with_matches > 0 else 0
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/queue")
async def get_reports_queue(
	admin_id: str = Depends(require_admin),
	limit: int = Query(50, ge=1, le=100),
	offset: int = Query(0, ge=0)
):
	client = get_supabase_client()
	
	try:
		reports = client.table("abuse_reports").select("id, reporter_id, reported_id, reason, status, created_at").eq("status", "pending").is_("deleted_at", None).order("created_at", desc=False).execute()
		
		paginated = reports.data[offset:offset + limit]
		
		return {
			"data": paginated,
			"total": len(reports.data),
			"limit": limit,
			"offset": offset
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
