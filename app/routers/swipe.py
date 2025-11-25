from fastapi import APIRouter, HTTPException, Depends, Body
from app.auth import verify_token
from supabase_client import get_supabase_client
from datetime import datetime
import uuid

router = APIRouter(prefix="/swipe", tags=["swipe"])

@router.post("/{target_user_id}/like")
async def like_user(
	target_user_id: str,
	user_id: str = Depends(verify_token)
):
	if user_id == target_user_id:
		raise HTTPException(status_code=400, detail="Cannot like yourself")
	
	client = get_supabase_client()
	
	try:
		target = client.table("users").select("id").eq("id", target_user_id).is_("deleted_at", None).single().execute()
		if not target.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		blocked = client.table("user_blocks").select("id").or_(
			f"blocker_id.eq.{user_id},blocked_id.eq.{target_user_id}",
			f"blocker_id.eq.{target_user_id},blocked_id.eq.{user_id}"
		).is_("deleted_at", None).single().execute()
		if blocked.data:
			raise HTTPException(status_code=403, detail="User is blocked")
		
		existing_action = client.table("user_actions").select("id").eq("user_id", user_id).eq("target_user_id", target_user_id).eq("action_type", "like").is_("deleted_at", None).single().execute()
		if existing_action.data:
			raise HTTPException(status_code=409, detail="Already liked this user")
		
		existing_match = client.table("matches").select("id").or_(
			f"user1.eq.{user_id},user2.eq.{target_user_id}",
			f"user1.eq.{target_user_id},user2.eq.{user_id}"
		).is_("deleted_at", None).single().execute()
		if existing_match.data:
			raise HTTPException(status_code=409, detail="Match already exists")
		
		resp = client.table("user_actions").insert({
			"user_id": user_id,
			"action_type": "like",
			"target_user_id": target_user_id,
			"status": "completed"
		}).select().execute()
		
		mutual_like = client.table("user_actions").select("id").eq("user_id", target_user_id).eq("target_user_id", user_id).eq("action_type", "like").is_("deleted_at", None).single().execute()
		
		if mutual_like.data:
			match_id = str(uuid.uuid4())
			client.table("matches").insert({
				"id": match_id,
				"user1": min(user_id, target_user_id),
				"user2": max(user_id, target_user_id),
				"compatibility_score": 0.0
			}).execute()
			
			return {
				"status": "liked",
				"mutual_match": True,
				"match_id": match_id
			}
		
		return {
			"status": "liked",
			"mutual_match": False
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/{target_user_id}/pass")
async def pass_user(
	target_user_id: str,
	user_id: str = Depends(verify_token)
):
	if user_id == target_user_id:
		raise HTTPException(status_code=400, detail="Cannot pass on yourself")
	
	client = get_supabase_client()
	
	try:
		target = client.table("users").select("id").eq("id", target_user_id).is_("deleted_at", None).single().execute()
		if not target.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		existing_action = client.table("user_actions").select("id").eq("user_id", user_id).eq("target_user_id", target_user_id).eq("action_type", "pass").is_("deleted_at", None).single().execute()
		if existing_action.data:
			raise HTTPException(status_code=409, detail="Already passed on this user")
		
		resp = client.table("user_actions").insert({
			"user_id": user_id,
			"action_type": "pass",
			"target_user_id": target_user_id,
			"status": "completed"
		}).select().execute()
		
		return {"status": "passed"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/{target_user_id}/undo")
async def undo_action(
	target_user_id: str,
	user_id: str = Depends(verify_token)
):
	if user_id == target_user_id:
		raise HTTPException(status_code=400, detail="Cannot undo action on yourself")
	
	client = get_supabase_client()
	
	try:
		last_action = client.table("user_actions").select("id, action_type, match_id").eq("user_id", user_id).eq("target_user_id", target_user_id).order("created_at", desc=True).limit(1).single().execute()
		
		if not last_action.data:
			raise HTTPException(status_code=404, detail="No previous action found")
		
		action = last_action.data
		
		if action["action_type"] == "like" and action["match_id"]:
			client.table("matches").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", action["match_id"]).execute()
		
		client.table("user_actions").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", action["id"]).execute()
		
		resp = client.table("user_actions").insert({
			"user_id": user_id,
			"action_type": "undo",
			"target_user_id": target_user_id,
			"status": "completed"
		}).select().execute()
		
		return {"status": "undone", "original_action": action["action_type"]}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
