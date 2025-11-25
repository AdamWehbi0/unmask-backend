from fastapi import APIRouter, HTTPException, Depends
from app.auth import verify_token
from app.schemas import RevealStatus, UserProfile
from supabase_client import get_supabase_client

router = APIRouter(prefix="/matches", tags=["reveal"])

@router.post("/{match_id}/reveal")
async def reveal_match(match_id: str, user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("matches").select("*").eq("id", match_id).single().execute()
		match = resp.data
		
		if user_id not in [match["user1"], match["user2"]]:
			raise HTTPException(status_code=403, detail="Unauthorized")
		
		reveal_col = "reveal_user1" if match["user1"] == user_id else "reveal_user2"
		
		if match[reveal_col]:
			raise HTTPException(status_code=409, detail="Already revealed")
		
		update_resp = client.table("matches").update({reveal_col: True}).eq("id", match_id).select().execute()
		updated_match = update_resp.data[0]
		
		both_revealed = updated_match["reveal_user1"] and updated_match["reveal_user2"]
		
		other_user_id = match["user2"] if match["user1"] == user_id else match["user1"]
		
		if both_revealed:
			other_user_resp = client.table("users").select("*").eq("id", other_user_id).is_("deleted_at", None).single().execute()
			other_user = other_user_resp.data
			return {
				"match_id": match_id,
				"both_revealed": True,
				"other_user": UserProfile(**other_user)
			}
		else:
			return {
				"match_id": match_id,
				"both_revealed": False,
				"other_user": None
			}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.get("/{match_id}/reveal-status", response_model=RevealStatus)
async def get_reveal_status(match_id: str, user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("matches").select("*").eq("id", match_id).single().execute()
		match = resp.data
		
		if user_id not in [match["user1"], match["user2"]]:
			raise HTTPException(status_code=403, detail="Unauthorized")
		
		both_revealed = match["reveal_user1"] and match["reveal_user2"]
		
		other_user_id = match["user2"] if match["user1"] == user_id else match["user1"]
		other_user = None
		
		if both_revealed:
			other_user_resp = client.table("users").select("*").eq("id", other_user_id).is_("deleted_at", None).single().execute()
			other_user = UserProfile(**other_user_resp.data)
		
		return {
			"match_id": match_id,
			"both_revealed": both_revealed,
			"other_user": other_user
		}
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))
