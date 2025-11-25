from fastapi import APIRouter, HTTPException, Depends, Query
from app.auth import verify_token
from supabase_client import get_supabase_client
from datetime import datetime

router = APIRouter(prefix="/users", tags=["blocking"])

@router.post("/{user_id}/block/{target_user_id}")
async def block_user(
	user_id: str,
	target_user_id: str,
	auth_user_id: str = Depends(verify_token)
):
	if user_id != auth_user_id:
		raise HTTPException(status_code=403, detail="Unauthorized")
	
	if user_id == target_user_id:
		raise HTTPException(status_code=400, detail="Cannot block yourself")
	
	client = get_supabase_client()
	
	try:
		target = client.table("users").select("id").eq("id", target_user_id).is_("deleted_at", None).single().execute()
		if not target.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		existing = client.table("user_blocks").select("id").eq("blocker_id", user_id).eq("blocked_id", target_user_id).is_("deleted_at", None).single().execute()
		if existing.data:
			raise HTTPException(status_code=409, detail="User already blocked")
		
		client.table("user_blocks").insert({
			"blocker_id": user_id,
			"blocked_id": target_user_id
		}).execute()
		
		matches = client.table("matches").select("id").or_(
			f"user1.eq.{user_id},user2.eq.{user_id}",
			f"user1.eq.{target_user_id},user2.eq.{target_user_id}"
		).is_("deleted_at", None).execute()
		
		for match in matches.data:
			client.table("matches").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", match["id"]).execute()
		
		return {"status": "blocked"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}/block/{target_user_id}")
async def unblock_user(
	user_id: str,
	target_user_id: str,
	auth_user_id: str = Depends(verify_token)
):
	if user_id != auth_user_id:
		raise HTTPException(status_code=403, detail="Unauthorized")
	
	client = get_supabase_client()
	
	try:
		block = client.table("user_blocks").select("id").eq("blocker_id", user_id).eq("blocked_id", target_user_id).is_("deleted_at", None).single().execute()
		if not block.data:
			raise HTTPException(status_code=404, detail="Block not found")
		
		client.table("user_blocks").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", block.data["id"]).execute()
		
		return {"status": "unblocked"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/blocked")
async def get_blocked_users(
	user_id: str,
	auth_user_id: str = Depends(verify_token),
	limit: int = Query(50, ge=1, le=100),
	offset: int = Query(0, ge=0)
):
	if user_id != auth_user_id:
		raise HTTPException(status_code=403, detail="Unauthorized")
	
	client = get_supabase_client()
	
	try:
		blocks = client.table("user_blocks").select("blocked_id").eq("blocker_id", user_id).is_("deleted_at", None).execute()
		blocked_ids = [b["blocked_id"] for b in blocks.data]
		
		if not blocked_ids:
			return {"data": [], "total": 0, "limit": limit, "offset": offset}
		
		users = client.table("users").select("id, email, traits, values").in_("id", blocked_ids).is_("deleted_at", None).execute()
		
		return {
			"data": users.data[offset:offset + limit],
			"total": len(users.data),
			"limit": limit,
			"offset": offset
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
