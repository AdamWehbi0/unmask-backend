"""
Fraud Detection System for UNMASK
Detects bots, fake profiles, and suspicious behavior
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from enum import Enum
from supabase_client import get_supabase_client

class FraudSeverity(str, Enum):
	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"

class FraudFlagType(str, Enum):
	RAPID_SWIPES = "rapid_swipes"
	SUSPICIOUS_PATTERN = "suspicious_pattern"
	LOW_ENGAGEMENT = "low_engagement"
	DUPLICATE_PHOTOS = "duplicate_photos"
	FAKE_LOCATION = "fake_location"
	BOT_BEHAVIOR = "bot_behavior"
	MASS_MESSAGES = "mass_messages"
	CATFISH_INDICATOR = "catfish_indicator"

def calculate_trust_score(user_data: Dict) -> Dict:
	"""
	Calculate multi-factor trust score for a user
	Returns dict with individual scores and overall trust_score (0-100)
	"""
	scores = {}
	
	# Account age score (higher is better)
	account_age_days = (datetime.utcnow() - user_data.get("created_at", datetime.utcnow())).days
	scores["account_age_score"] = min(account_age_days * 2, 25)  # Max 25 points
	
	# Photo verification score
	verified_photos = user_data.get("verified_photos", 0)
	scores["photo_verification_score"] = min(verified_photos * 15, 25)  # Max 25 points
	
	# Profile completeness
	profile_fields = [
		user_data.get("bio"),
		user_data.get("job_title"),
		user_data.get("education"),
	]
	profile_completeness = len([f for f in profile_fields if f]) / len(profile_fields) * 100
	scores["profile_completeness_score"] = (profile_completeness / 100) * 20  # Max 20 points
	
	# Message quality (approximation based on response rate)
	response_rate = user_data.get("message_response_rate", 0)
	scores["message_quality_score"] = (response_rate / 100) * 15  # Max 15 points
	
	# Behavior score (inverse of reports)
	reports_against = user_data.get("reports_against", 0)
	scores["behavior_score"] = max(15 - (reports_against * 5), 0)  # Max 15 points
	
	# Calculate overall trust score
	overall_score = sum(scores.values())
	scores["overall_trust_score"] = min(overall_score, 100)
	
	return scores

async def flag_user_for_fraud(
	user_id: str,
	flag_type: FraudFlagType,
	severity: FraudSeverity,
	details: Dict,
	flagged_by: str = "system"
) -> bool:
	"""
	Flag a user for potential fraud
	
	Args:
		user_id: User to flag
		flag_type: Type of fraud indicator
		severity: Severity level
		details: Additional context about the flag
		flagged_by: Who flagged (system or admin user_id)
	"""
	try:
		supabase = get_supabase_client()
		
		flag_record = {
			"user_id": user_id,
			"flag_type": flag_type.value,
			"severity": severity.value,
			"details": json.dumps(details),
			"flagged_by": flagged_by,
			"flagged_at": datetime.utcnow().isoformat(),
			"resolved": False,
		}
		
		result = supabase.table("fraud_flags").insert(flag_record).execute()
		return len(result.data) > 0
	except Exception as e:
		print(f"Error flagging user for fraud: {e}")
		return False

async def detect_rapid_swipes(user_id: str, window_minutes: int = 5, threshold: int = 30) -> Tuple[bool, Dict]:
	"""
	Detect if user is swiping too rapidly (bot indicator)
	
	Args:
		user_id: User to check
		window_minutes: Time window to analyze
		threshold: Max swipes allowed in window
		
	Returns:
		(is_suspicious, details_dict)
	"""
	try:
		supabase = get_supabase_client()
		cutoff_time = (datetime.utcnow() - timedelta(minutes=window_minutes)).isoformat()
		
		result = supabase.table("actions").select(
			"id",
			count="exact"
		).eq("user_id", user_id).eq("action_type", "swipe").gte("created_at", cutoff_time).execute()
		
		swipe_count = result.count or 0
		is_suspicious = swipe_count > threshold
		
		details = {
			"swipe_count": swipe_count,
			"time_window_minutes": window_minutes,
			"threshold": threshold,
			"swipes_per_minute": swipe_count / window_minutes,
		}
		
		return is_suspicious, details
	except Exception as e:
		print(f"Error detecting rapid swipes: {e}")
		return False, {"error": str(e)}

async def detect_duplicate_photos(user_id: str, hash_threshold: float = 0.95) -> Tuple[bool, Dict]:
	"""
	Detect if user has suspiciously similar photos (catfish indicator)
	
	Args:
		user_id: User to check
		hash_threshold: Similarity threshold (0-1)
		
	Returns:
		(has_duplicates, details_dict)
	"""
	try:
		supabase = get_supabase_client()
		
		# Get all user photos
		result = supabase.table("photo_uploads").select(
			"id,photo_hash"
		).eq("user_id", user_id).eq("deleted_at", None).execute()
		
		photos = result.data or []
		
		if len(photos) < 2:
			return False, {"photo_count": len(photos), "duplicates_found": 0}
		
		# Simple duplicate detection (in production, use image perceptual hashing)
		duplicates = 0
		for i, photo1 in enumerate(photos):
			for photo2 in photos[i+1:]:
				if photo1.get("photo_hash") == photo2.get("photo_hash"):
					duplicates += 1
		
		has_duplicates = duplicates > 0
		
		details = {
			"photo_count": len(photos),
			"duplicates_found": duplicates,
			"threshold": hash_threshold,
		}
		
		return has_duplicates, details
	except Exception as e:
		print(f"Error detecting duplicate photos: {e}")
		return False, {"error": str(e)}

async def detect_location_spoofing(user_id: str, max_distance_km: float = 100) -> Tuple[bool, Dict]:
	"""
	Detect if user's location jumps are suspiciously large (location spoofing indicator)
	
	Args:
		user_id: User to check
		max_distance_km: Max plausible distance per hour
		
	Returns:
		(is_spoofing, details_dict)
	"""
	try:
		supabase = get_supabase_client()
		
		# Get last 3 location updates
		result = supabase.table("locations").select(
			"id,latitude,longitude,created_at"
		).eq("user_id", user_id).order("created_at", desc=True).limit(3).execute()
		
		locations = result.data or []
		
		if len(locations) < 2:
			return False, {"location_updates": len(locations), "suspicious_jump": False}
		
		# Calculate distances between consecutive updates
		from math import radians, cos, sin, asin, sqrt
		
		def haversine(lon1, lat1, lon2, lat2):
			"""Calculate great circle distance between two points on earth (in km)"""
			lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
			dlon = lon2 - lon1
			dlat = lat2 - lat1
			a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
			c = 2 * asin(sqrt(a))
			r = 6371  # Radius of earth in kilometers
			return c * r
		
		suspicious_jumps = 0
		max_jump = 0
		
		for i in range(len(locations) - 1):
			loc1 = locations[i]
			loc2 = locations[i + 1]
			
			time_diff = (datetime.fromisoformat(loc1["created_at"]) - 
						datetime.fromisoformat(loc2["created_at"])).total_seconds() / 3600  # hours
			
			if time_diff > 0:
				distance = haversine(loc1["longitude"], loc1["latitude"], 
									 loc2["longitude"], loc2["latitude"])
				max_plausible = max_distance_km * time_diff
				
				if distance > max_plausible:
					suspicious_jumps += 1
					max_jump = max(max_jump, distance)
		
		is_spoofing = suspicious_jumps > 0
		
		details = {
			"location_updates_analyzed": len(locations),
			"suspicious_jumps": suspicious_jumps,
			"max_implausible_distance_km": max_jump,
			"max_plausible_speed_km_per_hour": max_distance_km,
		}
		
		return is_spoofing, details
	except Exception as e:
		print(f"Error detecting location spoofing: {e}")
		return False, {"error": str(e)}

async def detect_mass_messaging(user_id: str, window_hours: int = 1, threshold: int = 20) -> Tuple[bool, Dict]:
	"""
	Detect if user is mass messaging (spam indicator)
	
	Args:
		user_id: User to check
		window_hours: Time window to analyze
		threshold: Max messages allowed in window
		
	Returns:
		(is_mass_messaging, details_dict)
	"""
	try:
		supabase = get_supabase_client()
		cutoff_time = (datetime.utcnow() - timedelta(hours=window_hours)).isoformat()
		
		result = supabase.table("messages").select(
			"id",
			count="exact"
		).eq("sender_id", user_id).gte("created_at", cutoff_time).execute()
		
		message_count = result.count or 0
		is_mass_messaging = message_count > threshold
		
		details = {
			"message_count": message_count,
			"time_window_hours": window_hours,
			"threshold": threshold,
			"messages_per_hour": message_count / window_hours,
		}
		
		return is_mass_messaging, details
	except Exception as e:
		print(f"Error detecting mass messaging: {e}")
		return False, {"error": str(e)}

async def run_fraud_detection_scan(user_id: str) -> Dict:
	"""
	Run comprehensive fraud detection scan on user
	Returns dict with all detection results
	"""
	results = {
		"user_id": user_id,
		"scan_timestamp": datetime.utcnow().isoformat(),
		"detections": {},
		"flags_raised": 0,
	}
	
	# Rapid swipes check
	rapid_swipe_detected, rapid_swipe_details = await detect_rapid_swipes(user_id)
	if rapid_swipe_detected:
		results["detections"]["rapid_swipes"] = rapid_swipe_details
		results["flags_raised"] += 1
		await flag_user_for_fraud(
			user_id,
			FraudFlagType.RAPID_SWIPES,
			FraudSeverity.MEDIUM,
			rapid_swipe_details
		)
	
	# Duplicate photos check
	duplicate_detected, duplicate_details = await detect_duplicate_photos(user_id)
	if duplicate_detected:
		results["detections"]["duplicate_photos"] = duplicate_details
		results["flags_raised"] += 1
		await flag_user_for_fraud(
			user_id,
			FraudFlagType.DUPLICATE_PHOTOS,
			FraudSeverity.MEDIUM,
			duplicate_details
		)
	
	# Location spoofing check
	location_spoofing, location_details = await detect_location_spoofing(user_id)
	if location_spoofing:
		results["detections"]["location_spoofing"] = location_details
		results["flags_raised"] += 1
		await flag_user_for_fraud(
			user_id,
			FraudFlagType.FAKE_LOCATION,
			FraudSeverity.HIGH,
			location_details
		)
	
	# Mass messaging check
	mass_messaging, mass_messaging_details = await detect_mass_messaging(user_id)
	if mass_messaging:
		results["detections"]["mass_messaging"] = mass_messaging_details
		results["flags_raised"] += 1
		await flag_user_for_fraud(
			user_id,
			FraudFlagType.MASS_MESSAGES,
			FraudSeverity.HIGH,
			mass_messaging_details
		)
	
	return results
