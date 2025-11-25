from fastapi import APIRouter, HTTPException, Depends, Query
from app.auth import verify_token
from supabase_client import get_supabase_client
from app.services.matching import calculate_compatibility_score, get_recommendations
from datetime import datetime

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

@router.get("")
async def get_user_recommendations(
	user_id: str = Depends(verify_token),
	limit: int = Query(20, ge=1, le=100),
	offset: int = Query(0, ge=0)
):
	"""
	Get personalized recommendations sorted by compatibility score.
	Filters: blocked users, already matched, reported users.
	Applies user's saved filters.
	"""
	client = get_supabase_client()
	
	try:
		# Get user location
		user_loc = client.table("user_locations").select("latitude, longitude").eq("user_id", user_id).single().execute()
		if not user_loc.data:
			raise HTTPException(status_code=400, detail="Location not set. Please update your location first.")
		
		user_lat = float(user_loc.data["latitude"])
		user_lon = float(user_loc.data["longitude"])
		
		# Get user's filters
		filters_resp = client.table("user_filters").select("*").eq("user_id", user_id).single().execute()
		filters = filters_resp.data if filters_resp.data else {}
		
		# Get all verified, non-deleted users
		all_users = client.table("users").select(
			"users.id, users.age, users.gender, users.traits, users.values, users.is_verified, user_locations.latitude, user_locations.longitude"
		).eq("users.is_verified", True).is_("users.deleted_at", None).execute()
		
		# Get blocked, matched, reported users
		blocked = client.table("user_blocks").select("blocked_id").eq("blocker_id", user_id).is_("deleted_at", None).execute()
		blocked_ids = {b["blocked_id"] for b in blocked.data}
		
		matched = client.table("matches").select("user1, user2").or_(
			f"user1.eq.{user_id},user2.eq.{user_id}"
		).is_("deleted_at", None).execute()
		matched_ids = {
			m["user1"] if m["user1"] != user_id else m["user2"]
			for m in matched.data
		}
		
		reported = client.table("abuse_reports").select("reported_id").eq("reporter_id", user_id).is_("deleted_at", None).execute()
		reported_ids = {r["reported_id"] for r in reported.data}
		
		excluded_ids = blocked_ids | matched_ids | reported_ids | {user_id}
		
		# Filter candidates
		candidates = []
		for user_data in all_users.data:
			if user_data["id"] in excluded_ids:
				continue
			
			# Check age filter
			if user_data.get("age"):
				min_age = filters.get("min_age", 18)
				max_age = filters.get("max_age", 50)
				if not (min_age <= user_data["age"] <= max_age):
					continue
			
			# Check distance filter
			if user_data.get("latitude") and user_data.get("longitude"):
				from app.services.matching import haversine_distance
				target_lat = float(user_data["latitude"])
				target_lon = float(user_data["longitude"])
				distance_km = haversine_distance(user_lat, user_lon, target_lat, target_lon)
				
				max_distance = filters.get("max_distance_km", 30)
				if distance_km > max_distance:
					continue
			
			candidates.append(user_data)
		
		# Calculate compatibility scores
		recommendations = []
		for candidate in candidates:
			score, match_pct = await calculate_compatibility_score(user_id, candidate["id"])
			
			recommendations.append({
				"id": candidate["id"],
				"age": candidate.get("age"),
				"gender": candidate.get("gender"),
				"compatibility_score": round(score, 2),
				"match_percentage": round(match_pct, 2)
			})
		
		# Sort by compatibility score descending
		recommendations.sort(key=lambda x: x["compatibility_score"], reverse=True)
		
		# Apply pagination
		total_count = len(recommendations)
		paginated = recommendations[offset:offset + limit]
		
		# Log event
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "recommendations_viewed", {
			"limit": limit,
			"offset": offset,
			"total_available": total_count
		}))
		
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

@router.get("/{candidate_id}/compatibility")
async def get_compatibility_with_user(
	candidate_id: str,
	user_id: str = Depends(verify_token)
):
	"""Get detailed compatibility score between two users"""
	client = get_supabase_client()
	
	try:
		# Verify candidate exists
		candidate = client.table("users").select("id").eq("id", candidate_id).single().execute()
		if not candidate.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		# Check if blocked
		blocked = client.table("user_blocks").select("id").or_(
			f"blocker_id.eq.{user_id},blocked_id.eq.{candidate_id}",
			f"blocker_id.eq.{candidate_id},blocked_id.eq.{user_id}"
		).is_("deleted_at", None).single().execute()
		
		if blocked.data:
			raise HTTPException(status_code=403, detail="Cannot view compatibility")
		
		score, match_pct = await calculate_compatibility_score(user_id, candidate_id)
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "compatibility_viewed", {
			"candidate_id": candidate_id,
			"score": score
		}))
		
		return {
			"compatibility_score": round(score, 2),
			"match_percentage": round(match_pct, 2)
		}
	
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
