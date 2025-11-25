from fastapi import APIRouter, HTTPException, Depends, Query
from app.auth import verify_token
from supabase_client import get_supabase_client
from app.schemas import InterestCategory
from datetime import datetime
from typing import List

router = APIRouter(prefix="/interests", tags=["interests"])

# Predefined interest categories
INTERESTS_CATALOG = [
	("Travel", "Outdoors", "✈️"),
	("Hiking", "Outdoors", "⛰️"),
	("Camping", "Outdoors", "⛺"),
	("Beach Days", "Outdoors", "🏖️"),
	("Mountain Sports", "Outdoors", "🏔️"),
	
	("Fitness", "Health & Wellness", "💪"),
	("Yoga", "Health & Wellness", "🧘"),
	("Running", "Health & Wellness", "🏃"),
	("Dancing", "Health & Wellness", "💃"),
	("Meditation", "Health & Wellness", "🧘‍♀️"),
	
	("Cooking", "Food & Drink", "👨‍🍳"),
	("Foodie", "Food & Drink", "🍽️"),
	("Wine Tasting", "Food & Drink", "🍷"),
	("Coffee", "Food & Drink", "☕"),
	("Baking", "Food & Drink", "🍰"),
	
	("Music", "Arts & Entertainment", "🎵"),
	("Live Concerts", "Arts & Entertainment", "🎤"),
	("Playing Instruments", "Arts & Entertainment", "🎸"),
	("DJ", "Arts & Entertainment", "🎧"),
	("Karaoke", "Arts & Entertainment", "🎤"),
	
	("Art", "Arts & Entertainment", "🎨"),
	("Photography", "Arts & Entertainment", "📸"),
	("Painting", "Arts & Entertainment", "🖌️"),
	("Theater", "Arts & Entertainment", "🎭"),
	("Comedy", "Arts & Entertainment", "😂"),
	
	("Movies", "Entertainment", "🎬"),
	("TV Shows", "Entertainment", "📺"),
	("Gaming", "Entertainment", "🎮"),
	("Board Games", "Entertainment", "🎲"),
	("Anime", "Entertainment", "🎌"),
	
	("Reading", "Culture & Learning", "📚"),
	("Podcasts", "Culture & Learning", "🎙️"),
	("History", "Culture & Learning", "📜"),
	("Philosophy", "Culture & Learning", "🤔"),
	("Astronomy", "Culture & Learning", "🌌"),
	
	("Sports", "Sports", "⚽"),
	("Basketball", "Sports", "🏀"),
	("Tennis", "Sports", "🎾"),
	("Swimming", "Sports", "🏊"),
	("Cycling", "Sports", "🚴"),
	
	("Pet Lover", "Lifestyle", "🐾"),
	("Dog Person", "Lifestyle", "🐕"),
	("Cat Person", "Lifestyle", "🐈"),
	("Environmental Activist", "Lifestyle", "♻️"),
	("Volunteering", "Lifestyle", "🤝"),
	
	("Fashion", "Style & Beauty", "👗"),
	("Shopping", "Style & Beauty", "🛍️"),
	("Skincare", "Style & Beauty", "💄"),
	("Tattoos", "Style & Beauty", "🖤"),
	("Piercing", "Style & Beauty", "💎"),
	
	("Tech Geek", "Hobbies", "💻"),
	("DIY", "Hobbies", "🔨"),
	("Cars", "Hobbies", "🏎️"),
	("Motorcycles", "Hobbies", "🏍️"),
	("Gardening", "Hobbies", "🌱"),
]

@router.get("/categories", response_model=List[InterestCategory])
async def get_interest_categories():
	"""Get all available interest categories"""
	client = get_supabase_client()
	
	try:
		resp = client.table("interest_categories").select("*").execute()
		
		# If empty, populate with defaults
		if not resp.data:
			for name, category, emoji in INTERESTS_CATALOG:
				client.table("interest_categories").insert({
					"name": name,
					"category": category,
					"emoji": emoji
				}).execute()
			
			resp = client.table("interest_categories").select("*").execute()
		
		return resp.data
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories/search")
async def search_interest_categories(q: str = Query(""), category: str = Query("") ):
	"""Search interest categories by name or filter by category"""
	client = get_supabase_client()
	
	try:
		if q:
			resp = client.table("interest_categories").select("*").ilike("name", f"%{q}%").execute()
		elif category:
			resp = client.table("interest_categories").select("*").eq("category", category).execute()
		else:
			resp = client.table("interest_categories").select("*").execute()
		
		return resp.data
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/categories/{category_id}/add")
async def add_interest(
	category_id: str,
	user_id: str = Depends(verify_token)
):
	"""Add interest to user's profile"""
	client = get_supabase_client()
	
	try:
		# Check if interest exists
		interest = client.table("interest_categories").select("id").eq("id", category_id).single().execute()
		if not interest.data:
			raise HTTPException(status_code=404, detail="Interest not found")
		
		# Check if already added
		existing = client.table("user_interests").select("id").eq("user_id", user_id).eq("interest_id", category_id).single().execute()
		if existing.data:
			raise HTTPException(status_code=409, detail="Interest already added")
		
		# Add interest
		resp = client.table("user_interests").insert({
			"user_id": user_id,
			"interest_id": category_id
		}).select().execute()
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "interest_added", {"interest_id": category_id}))
		
		return resp.data[0]
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.delete("/categories/{category_id}/remove")
async def remove_interest(
	category_id: str,
	user_id: str = Depends(verify_token)
):
	"""Remove interest from user's profile"""
	client = get_supabase_client()
	
	try:
		interest = client.table("user_interests").select("id").eq("user_id", user_id).eq("interest_id", category_id).single().execute()
		if not interest.data:
			raise HTTPException(status_code=404, detail="Interest not found")
		
		client.table("user_interests").delete().eq("id", interest.data["id"]).execute()
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "interest_removed", {"interest_id": category_id}))
		
		return {"status": "removed"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}")
async def get_user_interests(
	user_id: str,
	auth_user_id: str = Depends(verify_token)
):
	"""Get user's selected interests"""
	client = get_supabase_client()
	
	try:
		resp = client.table("user_interests").select(
			"*, interest_categories(id, name, category, emoji)"
		).eq("user_id", user_id).execute()
		
		interests = [
			{
				"id": item["interest_categories"]["id"],
				"name": item["interest_categories"]["name"],
				"category": item["interest_categories"]["category"],
				"emoji": item["interest_categories"]["emoji"]
			}
			for item in resp.data
		]
		
		return {"interests": interests, "total": len(interests)}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/bulk-add")
async def bulk_add_interests(
	user_id: str,
	interest_ids: list[str],
	auth_user_id: str = Depends(verify_token)
):
	"""Add multiple interests at once"""
	if user_id != auth_user_id:
		raise HTTPException(status_code=403, detail="Unauthorized")
	
	client = get_supabase_client()
	
	try:
		# Get existing interests
		existing = client.table("user_interests").select("interest_id").eq("user_id", user_id).execute()
		existing_ids = {e["interest_id"] for e in existing.data}
		
		# Filter out duplicates
		new_interest_ids = [id for id in interest_ids if id not in existing_ids]
		
		if not new_interest_ids:
			return {"status": "no_new_interests", "added": 0}
		
		# Insert new interests
		inserts = [
			{"user_id": user_id, "interest_id": id}
			for id in new_interest_ids
		]
		
		client.table("user_interests").insert(inserts).execute()
		
		from app.services.analytics import log_event
		import asyncio
		asyncio.create_task(log_event(user_id, "interests_added_bulk", {"count": len(new_interest_ids)}))
		
		return {"status": "success", "added": len(new_interest_ids)}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
