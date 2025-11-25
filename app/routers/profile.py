from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from app.auth import verify_token
from supabase_client import get_supabase_client
from app.schemas import UserFilters, ProfileCompletion
from datetime import datetime
from pydantic import BaseModel

class PetsRequest(BaseModel):
	has_dogs: bool = False
	has_cats: bool = False
	has_other_pets: bool = False
	other_pets_description: Optional[str] = None
	likes_dogs: bool = True
	likes_cats: bool = True
	wants_pet: bool = False
	pet_allergies: Optional[str] = None

class LifestyleRequest(BaseModel):
	smoking: Optional[str] = None
	drinking: Optional[str] = None
	drugs: Optional[str] = None
	sleep_schedule: Optional[str] = None
	diet: Optional[str] = None
	exercise_frequency: Optional[str] = None
	social_lifestyle: Optional[str] = None

class GoalsRequest(BaseModel):
	wants_kids: Optional[str] = None
	marriage_timeline: Optional[str] = None
	relationship_type: Optional[str] = None
	career_ambition: Optional[str] = None
	travel_frequency: Optional[str] = None
	financial_goals: Optional[str] = None

router = APIRouter(prefix="/profile", tags=["profile"])

PROFILE_SECTIONS = {
	"basic": ["email", "age", "gender"],
	"appearance": ["height_cm", "bio"],
	"interests": ["interests"],
	"personality": ["traits", "values"],
	"lifestyle": ["smoking", "drinking", "diet", "exercise_frequency"],
	"goals": ["wants_kids", "marriage_timeline", "relationship_type"],
	"preferences": ["looking_for", "religion", "politics"],
	"career": ["education", "job_title", "company"],
	"pets": ["has_dogs", "has_cats", "likes_dogs"]
}

@router.get("/completion")
async def get_profile_completion(user_id: str = Depends(verify_token)):
	"""Get profile completion status and guidance"""
	client = get_supabase_client()
	
	try:
		user = client.table("users").select("*").eq("id", user_id).single().execute().data
		if not user:
			raise HTTPException(status_code=404, detail="User not found")
		
		completed_sections = []
		missing_sections = []
		
		for section, fields in PROFILE_SECTIONS.items():
			section_complete = True
			
			if section == "basic":
				section_complete = bool(user.get("age") and user.get("gender"))
			
			elif section == "appearance":
				section_complete = bool(user.get("height_cm") and user.get("bio"))
			
			elif section == "interests":
				interests = client.table("user_interests").select("id").eq("user_id", user_id).execute()
				section_complete = len(interests.data) >= 3
			
			elif section == "personality":
				traits = user.get("traits") or []
				values = user.get("values") or []
				section_complete = len(traits) >= 2 and len(values) >= 2
			
			elif section == "lifestyle":
				lifestyle = client.table("user_lifestyle").select("id").eq("user_id", user_id).single().execute().data
				section_complete = lifestyle is not None
			
			elif section == "goals":
				goals = client.table("user_goals").select("id").eq("user_id", user_id).single().execute().data
				section_complete = goals is not None
			
			elif section == "preferences":
				looking_for = user.get("looking_for") or []
				section_complete = len(looking_for) > 0 and bool(user.get("religion") or user.get("politics"))
			
			elif section == "career":
				section_complete = bool(user.get("job_title"))
			
			elif section == "pets":
				pets = client.table("user_pets").select("id").eq("user_id", user_id).single().execute().data
				section_complete = pets is not None
			
			if section_complete:
				completed_sections.append(section)
			else:
				missing_sections.append(section)
		
		completion_pct = int((len(completed_sections) / len(PROFILE_SECTIONS)) * 100)
		
		return ProfileCompletion(
			sections_completed=completed_sections,
			sections_remaining=missing_sections,
			completion_percentage=completion_pct
		)
	
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/pets")
async def update_pets(
	pets: PetsRequest,
	user_id: str = Depends(verify_token)
):
	"""Update or create user's pet preferences"""
	client = get_supabase_client()
	
	try:
		existing = client.table("user_pets").select("id").eq("user_id", user_id).single().execute()
		
		data = {
			"has_dogs": pets.has_dogs,
			"has_cats": pets.has_cats,
			"has_other_pets": pets.has_other_pets,
			"other_pets_description": pets.other_pets_description,
			"likes_dogs": pets.likes_dogs,
			"likes_cats": pets.likes_cats,
			"wants_pet": pets.wants_pet,
			"pet_allergies": pets.pet_allergies,
			"updated_at": datetime.utcnow().isoformat()
		}
		
		if existing.data:
			resp = client.table("user_pets").update(data).eq("user_id", user_id).select().execute()
		else:
			data["user_id"] = user_id
			resp = client.table("user_pets").insert(data).select().execute()
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "pets_updated", {}))
		
		return resp.data[0]
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/pets")
async def get_pets(user_id: str = Depends(verify_token)):
	"""Get user's pet preferences"""
	client = get_supabase_client()
	
	try:
		resp = client.table("user_pets").select("*").eq("user_id", user_id).single().execute()
		
		if not resp.data:
			return None
		
		return resp.data
	except Exception:
		return None

@router.post("/lifestyle")
async def update_lifestyle(
	lifestyle: LifestyleRequest,
	user_id: str = Depends(verify_token)
):
	"""Update or create user's lifestyle preferences"""
	client = get_supabase_client()
	
	try:
		existing = client.table("user_lifestyle").select("id").eq("user_id", user_id).single().execute()
		
		data = {
			"smoking": lifestyle.smoking,
			"drinking": lifestyle.drinking,
			"drugs": lifestyle.drugs,
			"sleep_schedule": lifestyle.sleep_schedule,
			"diet": lifestyle.diet,
			"exercise_frequency": lifestyle.exercise_frequency,
			"social_lifestyle": lifestyle.social_lifestyle,
			"updated_at": datetime.utcnow().isoformat()
		}
		
		if existing.data:
			resp = client.table("user_lifestyle").update(data).eq("user_id", user_id).select().execute()
		else:
			data["user_id"] = user_id
			resp = client.table("user_lifestyle").insert(data).select().execute()
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "lifestyle_updated", {}))
		
		return resp.data[0]
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/lifestyle")
async def get_lifestyle(user_id: str = Depends(verify_token)):
	"""Get user's lifestyle preferences"""
	client = get_supabase_client()
	
	try:
		resp = client.table("user_lifestyle").select("*").eq("user_id", user_id).single().execute()
		
		if not resp.data:
			return None
		
		return resp.data
	except Exception:
		return None

@router.post("/goals")
async def update_goals(
	goals: GoalsRequest,
	user_id: str = Depends(verify_token)
):
	"""Update or create user's life goals"""
	client = get_supabase_client()
	
	try:
		existing = client.table("user_goals").select("id").eq("user_id", user_id).single().execute()
		
		data = {
			"wants_kids": goals.wants_kids,
			"marriage_timeline": goals.marriage_timeline,
			"relationship_type": goals.relationship_type,
			"career_ambition": goals.career_ambition,
			"travel_frequency": goals.travel_frequency,
			"financial_goals": goals.financial_goals,
			"updated_at": datetime.utcnow().isoformat()
		}
		
		if existing.data:
			resp = client.table("user_goals").update(data).eq("user_id", user_id).select().execute()
		else:
			data["user_id"] = user_id
			resp = client.table("user_goals").insert(data).select().execute()
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "goals_updated", {}))
		
		return resp.data[0]
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/goals")
async def get_goals(user_id: str = Depends(verify_token)):
	"""Get user's life goals"""
	client = get_supabase_client()
	
	try:
		resp = client.table("user_goals").select("*").eq("user_id", user_id).single().execute()
		
		if not resp.data:
			return None
		
		return resp.data
	except Exception:
		return None

@router.post("/filters")
async def save_filters(
	filters: UserFilters,
	user_id: str = Depends(verify_token)
):
	"""Save search preferences"""
	client = get_supabase_client()
	
	try:
		existing = client.table("user_filters").select("id").eq("user_id", user_id).single().execute()
		
		data = {
			"min_age": filters.min_age,
			"max_age": filters.max_age,
			"max_distance_km": filters.max_distance_km,
			"relationship_types": filters.relationship_types or [],
			"preferred_interests": filters.preferred_interests or [],
			"preferred_goals": filters.preferred_goals or [],
			"show_only_verified": filters.show_only_verified,
			"show_only_with_photo": filters.show_only_with_photo,
			"updated_at": datetime.utcnow().isoformat()
		}
		
		if existing.data:
			resp = client.table("user_filters").update(data).eq("user_id", user_id).select().execute()
		else:
			data["user_id"] = user_id
			resp = client.table("user_filters").insert(data).select().execute()
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "filters_saved", {}))
		
		return resp.data[0]
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/filters")
async def get_filters(user_id: str = Depends(verify_token)):
	"""Get saved search preferences"""
	client = get_supabase_client()
	
	try:
		resp = client.table("user_filters").select("*").eq("user_id", user_id).single().execute()
		
		if not resp.data:
			# Return defaults
			return UserFilters()
		
		return resp.data
	except Exception:
		return UserFilters()
