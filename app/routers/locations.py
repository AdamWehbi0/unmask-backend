from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from supabase_client import get_supabase_client
from app.auth import verify_token

router = APIRouter(prefix="/locations", tags=["locations"])

class LocationUpdate(BaseModel):
	latitude: float
	longitude: float
	accuracy_meters: Optional[int] = None

@router.post("/update")
async def update_location(location: LocationUpdate, user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("user_locations").upsert({
			"user_id": user_id,
			"latitude": location.latitude,
			"longitude": location.longitude,
			"accuracy_meters": location.accuracy_meters,
			"updated_at": datetime.utcnow().isoformat()
		}, on_conflict="user_id").select().execute()
		
		client.table("users").update({
			"last_location_update": datetime.utcnow().isoformat()
		}).eq("id", user_id).execute()
		
		return {"status": "updated", "latitude": location.latitude, "longitude": location.longitude}
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.get("/current")
async def get_current_location(user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("user_locations").select("*").eq("user_id", user_id).single().execute()
		return resp.data
	except Exception:
		raise HTTPException(status_code=404, detail="Location not set")
