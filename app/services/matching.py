from supabase_client import get_supabase_client
from datetime import datetime
import math

async def calculate_compatibility_score(user1_id: str, user2_id: str) -> tuple[float, float]:
	"""
	Calculate compatibility score between two users.
	
	Returns: (compatibility_score: 0-100, match_percentage: 0-100)
	
	Factors:
	- Shared interests (40%)
	- Shared values (30%)
	- Location proximity (15%)
	- Lifestyle match (10%)
	- Life goals alignment (5%)
	"""
	client = get_supabase_client()
	
	try:
		# Get user data
		user1 = client.table("users").select("*").eq("id", user1_id).single().execute().data
		user2 = client.table("users").select("*").eq("id", user2_id).single().execute().data
		
		if not user1 or not user2:
			return 0.0, 0.0
		
		score = 0.0
		
		# 1. Shared interests (40%)
		interests1 = client.table("user_interests").select("interest_id").eq("user_id", user1_id).execute().data
		interests2 = client.table("user_interests").select("interest_id").eq("user_id", user2_id).execute().data
		
		interests1_set = {i["interest_id"] for i in interests1}
		interests2_set = {i["interest_id"] for i in interests2}
		
		if interests1_set and interests2_set:
			shared_interests = len(interests1_set & interests2_set)
			total_interests = max(len(interests1_set), len(interests2_set))
			interest_score = (shared_interests / total_interests) * 40 if total_interests > 0 else 0
		else:
			interest_score = 0
		
		# 2. Shared values (30%)
		values1_set = set(user1.get("values", []) or [])
		values2_set = set(user2.get("values", []) or [])
		
		if values1_set and values2_set:
			shared_values = len(values1_set & values2_set)
			total_values = max(len(values1_set), len(values2_set))
			values_score = (shared_values / total_values) * 30 if total_values > 0 else 0
		else:
			values_score = 0
		
		# 3. Location proximity (15%)
		try:
			loc1 = client.table("user_locations").select("latitude, longitude").eq("user_id", user1_id).single().execute().data
			loc2 = client.table("user_locations").select("latitude, longitude").eq("user_id", user2_id).single().execute().data
			
			if loc1 and loc2:
				# Distance in km using haversine
				lat1, lon1 = float(loc1["latitude"]), float(loc1["longitude"])
				lat2, lon2 = float(loc2["latitude"]), float(loc2["longitude"])
				
				distance_km = haversine_distance(lat1, lon1, lat2, lon2)
				
				# Closer = better (max 30km for 15 points)
				location_score = max(0, (1 - min(distance_km, 30) / 30) * 15)
			else:
				location_score = 0
		except:
			location_score = 0
		
		# 4. Lifestyle match (10%)
		lifestyle1 = client.table("user_lifestyle").select("*").eq("user_id", user1_id).single().execute().data
		lifestyle2 = client.table("user_lifestyle").select("*").eq("user_id", user2_id).single().execute().data
		
		lifestyle_score = 0
		if lifestyle1 and lifestyle2:
			matches = 0
			checks = 0
			
			fields_to_check = ["smoking", "drinking", "diet", "social_lifestyle"]
			for field in fields_to_check:
				if field in lifestyle1 and field in lifestyle2:
					checks += 1
					if lifestyle1[field] == lifestyle2[field]:
						matches += 1
			
			if checks > 0:
				lifestyle_score = (matches / checks) * 10
		
		# 5. Life goals alignment (5%)
		goals1 = client.table("user_goals").select("*").eq("user_id", user1_id).single().execute().data
		goals2 = client.table("user_goals").select("*").eq("user_id", user2_id).single().execute().data
		
		goals_score = 0
		if goals1 and goals2:
			matches = 0
			checks = 0
			
			fields_to_check = ["wants_kids", "marriage_timeline", "relationship_type"]
			for field in fields_to_check:
				if field in goals1 and field in goals2:
					checks += 1
					if goals1[field] == goals2[field]:
						matches += 1
			
			if checks > 0:
				goals_score = (matches / checks) * 5
		
		# Total score (0-100)
		total_score = interest_score + values_score + location_score + lifestyle_score + goals_score
		
		return total_score, total_score
	
	except Exception as e:
		print(f"Error calculating compatibility: {e}")
		return 0.0, 0.0

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	"""Calculate distance in km between two points using Haversine formula"""
	R = 6371  # Earth's radius in km
	
	lat1_rad = math.radians(lat1)
	lat2_rad = math.radians(lat2)
	delta_lat = math.radians(lat2 - lat1)
	delta_lon = math.radians(lon2 - lon1)
	
	a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	
	return R * c

async def get_recommendations(user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
	"""
	Get ranked recommendations based on compatibility score.
	Filters out: blocked users, already matched, reported users.
	Applies user's saved filters.
	"""
	client = get_supabase_client()
	
	try:
		# Get user and their filters
		user = client.table("users").select("*").eq("id", user_id).single().execute().data
		if not user:
			return []
		
		filters = client.table("user_filters").select("*").eq("user_id", user_id).single().execute().data
		
		# Get all potential matches
		all_users = client.table("users").select("id, age, traits, values").eq("is_verified", True).is_("deleted_at", None).execute().data
		
		# Get blocked, matched, and reported users
		blocked = client.table("user_blocks").select("blocked_id").eq("blocker_id", user_id).is_("deleted_at", None).execute().data
		blocked_ids = {b["blocked_id"] for b in blocked}
		
		matched = client.table("matches").select("user1, user2").or_(
			f"user1.eq.{user_id},user2.eq.{user_id}"
		).is_("deleted_at", None).execute().data
		matched_ids = {m.get("user1") or m.get("user2") for m in matched if m.get("user1") != user_id and m.get("user2") != user_id}
		
		reported = client.table("abuse_reports").select("reported_id").eq("reporter_id", user_id).is_("deleted_at", None).execute().data
		reported_ids = {r["reported_id"] for r in reported}
		
		excluded_ids = blocked_ids | matched_ids | reported_ids | {user_id}
		
		# Filter candidates
		candidates = []
		for candidate in all_users:
			if candidate["id"] in excluded_ids:
				continue
			
			# Apply age filter
			if filters:
				if candidate.get("age"):
					if not (filters.get("min_age", 18) <= candidate["age"] <= filters.get("max_age", 50)):
						continue
			
			candidates.append(candidate)
		
		# Calculate compatibility scores
		recommendations = []
		for candidate in candidates:
			score, match_pct = await calculate_compatibility_score(user_id, candidate["id"])
			recommendations.append({
				"id": candidate["id"],
				"score": score,
				"match_percentage": match_pct
			})
		
		# Sort by score descending
		recommendations.sort(key=lambda x: x["score"], reverse=True)
		
		# Apply pagination
		paginated = recommendations[offset:offset + limit]
		
		return paginated
	
	except Exception as e:
		print(f"Error getting recommendations: {e}")
		return []
