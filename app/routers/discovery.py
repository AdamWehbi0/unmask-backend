from fastapi import APIRouter, HTTPException, Depends, Query
from app.auth import verify_token
from app.schemas import UserProfile
from supabase_client import get_supabase_client
from geopy.distance import geodesic
from datetime import datetime
from app.services.matching import calculate_compatibility_score

router = APIRouter(prefix="/discovery", tags=["discovery"])

@router.get("", response_model=dict)
async def get_discovery(
	user_id: str = Depends(verify_token),
	distance_km: int = Query(20, ge=1, le=500),
	limit: int = Query(20, ge=1, le=100),
	offset: int = Query(0, ge=0),
	min_age: int = Query(18, ge=18, le=100),
	max_age: int = Query(50, ge=18, le=100),
	sort_by: str = Query("distance", regex="^(distance|compatibility)$")
):
	client = get_supabase_client()
	
	try:
		user_loc = client.table("user_locations").select("latitude, longitude").eq("user_id", user_id).single().execute()
		if not user_loc.data:
			raise HTTPException(status_code=400, detail="User location not set")
		
		user_lat = float(user_loc.data["latitude"])
		user_lon = float(user_loc.data["longitude"])
		
		all_users = client.table("users").select(
			"users.id, users.email, users.traits, users.values, users.green_flags, users.red_flags, users.lifestyle, users.created_at, user_locations.latitude, user_locations.longitude"
		).eq("users.is_verified", True).is_("users.deleted_at", None).execute()
		
		candidates = []
		for usr in all_users.data:
			if usr["id"] == user_id:
				continue
			
			target_lat = float(usr["latitude"])
			target_lon = float(usr["longitude"])
			dist = geodesic((user_lat, user_lon), (target_lat, target_lon)).kilometers
			
			if dist > distance_km:
				continue
			
			candidates.append({
				"id": usr["id"],
				"email": usr["email"],
				"traits": usr["traits"] or [],
				"values": usr["values"] or [],
				"green_flags": usr["green_flags"] or [],
				"red_flags": usr["red_flags"] or [],
				"lifestyle": usr["lifestyle"] or [],
				"distance_km": round(dist, 1),
				"created_at": usr["created_at"]
			})
		
		blocked_ids = client.table("user_blocks").select("blocked_id").eq("blocker_id", user_id).is_("deleted_at", None).execute()
		blocked_set = {b["blocked_id"] for b in blocked_ids.data}
		
		matched_ids = client.table("matches").select("user2").eq("user1", user_id).is_("deleted_at", None).execute()
		matched_ids.extend(client.table("matches").select("user1").eq("user2", user_id).is_("deleted_at", None).execute().data)
		matched_set = {m.get("user2") or m.get("user1") for m in matched_ids.data}
		
		reported_ids = client.table("abuse_reports").select("reported_id").eq("reporter_id", user_id).is_("deleted_at", None).execute()
		reported_set = {r["reported_id"] for r in reported_ids.data}
		
		filtered = [c for c in candidates if c["id"] not in blocked_set and c["id"] not in matched_set and c["id"] not in reported_set]
		
		# Add match percentage for each candidate
		for candidate in filtered:
			score, match_pct = await calculate_compatibility_score(user_id, candidate["id"])
			candidate["match_percentage"] = round(match_pct, 2)
		
		# Sort
		if sort_by == "compatibility":
			filtered.sort(key=lambda x: x["match_percentage"], reverse=True)
		else:
			filtered.sort(key=lambda x: x["distance_km"])
		
		total_count = len(filtered)
		paginated = filtered[offset:offset + limit]
		
		return {
			"data": paginated,
			"total": total_count,
			"limit": limit,
			"offset": offset
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
