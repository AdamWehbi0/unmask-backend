from fastapi import APIRouter, HTTPException, Depends
from app.auth import verify_token
from supabase_client import get_supabase_client
from pydantic import BaseModel

class RegisterDeviceRequest(BaseModel):
	device_token: str
	platform: str

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.post("/register-device")
async def register_device(
	request: RegisterDeviceRequest,
	user_id: str = Depends(verify_token)
):
	if request.platform not in ["ios", "android"]:
		raise HTTPException(status_code=400, detail="Invalid platform. Must be 'ios' or 'android'")
	
	client = get_supabase_client()
	
	try:
		existing = client.table("notification_tokens").select("id").eq("user_id", user_id).eq("device_token", request.device_token).is_("deleted_at", None).single().execute()
		
		if existing.data:
			return {"status": "already_registered"}
		
		resp = client.table("notification_tokens").insert({
			"user_id": user_id,
			"device_token": request.device_token,
			"platform": request.platform
		}).select().execute()
		
		return {"status": "registered", "data": resp.data[0]}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/deregister-device")
async def deregister_device(
	request: RegisterDeviceRequest,
	user_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		token = client.table("notification_tokens").select("id").eq("user_id", user_id).eq("device_token", request.device_token).is_("deleted_at", None).single().execute()
		
		if not token.data:
			raise HTTPException(status_code=404, detail="Device token not found")
		
		from datetime import datetime
		client.table("notification_tokens").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", token.data["id"]).execute()
		
		return {"status": "deregistered"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
