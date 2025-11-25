from fastapi import APIRouter, HTTPException, Depends
from app.auth import verify_token
from app.schemas import MatchResponse, UserAnonymous
from supabase_client import get_supabase_client
from typing import List
from geopy.distance import geodesic
from app.services.matching import calculate_compatibility_score

router = APIRouter(prefix="/matches", tags=["matches"])

def get_other_user_id(match: dict, user_id: str) -> str:
	return match["user2"] if match["user1"] == user_id else match["user1"]

@router.get("", response_model=List[MatchResponse])
async def get_user_matches(distance_km: int = 20, user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("matches").select("*").or_(f"user1.eq.{user_id},user2.eq.{user_id}").is_("deleted_at", None).execute()
		matches = resp.data
		
		my_location = client.table("user_locations").select("latitude, longitude").eq("user_id", user_id).single().execute()
		my_lat, my_lon = my_location.data["latitude"], my_location.data["longitude"]
		
		result = []
		for match in matches:
			other_user_id = get_other_user_id(match, user_id)
			other_user_resp = client.table("users").select("id,traits,values").eq("id", other_user_id).is_("deleted_at", None).single().execute()
			other_user = other_user_resp.data
			
			other_location = client.table("user_locations").select("latitude, longitude").eq("user_id", other_user_id).single().execute()
			other_lat, other_lon = other_location.data["latitude"], other_location.data["longitude"]
			
			distance = geodesic((my_lat, my_lon), (other_lat, other_lon)).km
			
			if distance <= distance_km:
				score, match_pct = await calculate_compatibility_score(user_id, other_user_id)
				
				result.append({
					"id": match["id"],
					"other_user_id": other_user_id,
					"other_user": UserAnonymous(**other_user),
					"compatibility_score": score,
					"match_percentage": match_pct,
					"both_revealed": match["reveal_user1"] and match["reveal_user2"],
					"distance_km": round(distance, 1),
					"created_at": match["created_at"]
				})
		
		return result
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(match_id: str, user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("matches").select("*").eq("id", match_id).single().execute()
		match = resp.data
		
		if user_id not in [match["user1"], match["user2"]]:
			raise HTTPException(status_code=403, detail="Unauthorized")
		
		other_user_id = get_other_user_id(match, user_id)
		other_user_resp = client.table("users").select("id,traits,values").eq("id", other_user_id).single().execute()
		other_user = other_user_resp.data
		
		score, match_pct = await calculate_compatibility_score(user_id, other_user_id)
		
		return {
			"id": match["id"],
			"other_user_id": other_user_id,
			"other_user": UserAnonymous(**other_user),
			"compatibility_score": score,
			"match_percentage": match_pct,
			"both_revealed": match["reveal_user1"] and match["reveal_user2"],
			"created_at": match["created_at"]
		}
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))
