from fastapi import APIRouter, HTTPException, Depends
from app.auth import verify_token
from app.schemas import UserCreate, UserProfile, UserUpdate
from supabase_client import get_supabase_client
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserProfile)
async def create_user(user: UserCreate, user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("users").insert({
			"id": user_id,
			"email": user.email,
			"traits": user.traits or [],
			"values": user.values or [],
			"green_flags": user.green_flags or [],
			"red_flags": user.red_flags or [],
			"lifestyle": user.lifestyle or [],
			"profile_complete": False,
		}).select().execute()
		return resp.data[0]
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.get("/{user_id}", response_model=UserProfile)
async def get_user(user_id: str, auth_user_id: str = Depends(verify_token)):
	if user_id != auth_user_id:
		raise HTTPException(status_code=403, detail="Unauthorized")
	
	client = get_supabase_client()
	try:
		resp = client.table("users").select("*").eq("id", user_id).is_("deleted_at", None).single().execute()
		return resp.data
	except Exception:
		raise HTTPException(status_code=404, detail="User not found")

@router.put("/{user_id}", response_model=UserProfile)
async def update_user(user_id: str, user: UserUpdate, auth_user_id: str = Depends(verify_token)):
	if user_id != auth_user_id:
		raise HTTPException(status_code=403, detail="Unauthorized")
	
	client = get_supabase_client()
	update_data = {k: v for k, v in user.dict().items() if v is not None}
	update_data["updated_at"] = datetime.utcnow().isoformat()
	
	try:
		resp = client.table("users").update(update_data).eq("id", user_id).select().execute()
		return resp.data[0]
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}")
async def delete_user(user_id: str, auth_user_id: str = Depends(verify_token)):
	if user_id != auth_user_id:
		raise HTTPException(status_code=403, detail="Unauthorized")
	
	client = get_supabase_client()
	try:
		client.table("users").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", user_id).execute()
		return {"status": "deleted"}
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))
