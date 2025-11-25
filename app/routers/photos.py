"""
Photos Router
Upload, manage, and retrieve user photos
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List
from datetime import datetime
from app.services.photo_service import (
	upload_photo,
	delete_photo,
	reorder_photos,
	get_user_photos,
	get_photo_by_id,
	set_primary_photo,
	get_user_photo_count,
	MAX_PHOTOS_PER_USER
)

router = APIRouter(prefix="/photos", tags=["Photos"])

async def get_current_user() -> str:
	"""Placeholder for auth - replace with real auth dependency"""
	return "user-id"

@router.post("/upload")
async def upload_user_photo(
	file: UploadFile = File(...),
	is_primary: bool = Form(False),
	current_user: str = Depends(get_current_user)
):
	"""
	Upload a new photo
	
	Query params:
		- is_primary: Set as profile/primary photo
		
	Returns:
		Photo record with URLs
	"""
	try:
		# Read file data
		content = await file.read()
		content_type = file.content_type or "image/jpeg"
		
		# Upload and process photo
		photo = await upload_photo(current_user, content, content_type, is_primary)
		
		if not photo:
			raise HTTPException(status_code=400, detail="Failed to upload photo")
		
		return {
			"status": "uploaded",
			"photo": {
				"id": photo["id"],
				"thumbnail_url": photo.get("thumbnail_url"),
				"medium_url": photo.get("medium_url"),
				"full_url": photo.get("full_url"),
				"is_primary": photo.get("is_primary"),
				"photo_order": photo.get("photo_order"),
				"created_at": photo.get("created_at"),
			}
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error uploading photo: {e}")

@router.get("/list")
async def list_user_photos(
	limit: int = 20,
	offset: int = 0,
	current_user: str = Depends(get_current_user)
):
	"""
	Get user's photos in order
	
	Query params:
		- limit: Max photos to return (default 20)
		- offset: Pagination offset (default 0)
	"""
	try:
		photos = await get_user_photos(current_user, limit, offset)
		
		return {
			"user_id": current_user,
			"photos": [
				{
					"id": p["id"],
					"thumbnail_url": p.get("thumbnail_url"),
					"medium_url": p.get("medium_url"),
					"full_url": p.get("full_url"),
					"is_primary": p.get("is_primary"),
					"photo_order": p.get("photo_order"),
					"created_at": p.get("created_at"),
				}
				for p in photos
			],
			"count": len(photos),
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error fetching photos: {e}")

@router.delete("/{photo_id}")
async def delete_user_photo(
	photo_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Delete a photo
	If it was primary, next photo becomes primary
	"""
	try:
		success = await delete_photo(photo_id, current_user)
		
		if not success:
			raise HTTPException(status_code=404, detail="Photo not found")
		
		return {
			"status": "deleted",
			"photo_id": photo_id,
			"deleted_at": datetime.utcnow().isoformat(),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error deleting photo: {e}")

@router.put("/reorder")
async def reorder_user_photos(
	photo_ids: List[str],
	current_user: str = Depends(get_current_user)
):
	"""
	Reorder photos
	
	Body: {"photo_ids": ["id1", "id2", "id3"]}
	"""
	try:
		if not photo_ids:
			raise HTTPException(status_code=400, detail="photo_ids required")
		
		success = await reorder_photos(current_user, photo_ids)
		
		if not success:
			raise HTTPException(status_code=400, detail="Invalid photo IDs")
		
		return {
			"status": "reordered",
			"photo_ids": photo_ids,
			"updated_at": datetime.utcnow().isoformat(),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error reordering photos: {e}")

@router.put("/{photo_id}/set-primary")
async def set_user_primary_photo(
	photo_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Set a photo as the user's primary/profile photo
	"""
	try:
		success = await set_primary_photo(photo_id, current_user)
		
		if not success:
			raise HTTPException(status_code=404, detail="Photo not found")
		
		return {
			"status": "updated",
			"photo_id": photo_id,
			"is_primary": True,
			"updated_at": datetime.utcnow().isoformat(),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error setting primary photo: {e}")

@router.get("/{photo_id}")
async def get_photo(
	photo_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Get specific photo details
	"""
	try:
		photo = await get_photo_by_id(photo_id, current_user)
		
		if not photo:
			raise HTTPException(status_code=404, detail="Photo not found")
		
		return {
			"id": photo["id"],
			"thumbnail_url": photo.get("thumbnail_url"),
			"medium_url": photo.get("medium_url"),
			"full_url": photo.get("full_url"),
			"is_primary": photo.get("is_primary"),
			"photo_order": photo.get("photo_order"),
			"file_size": photo.get("file_size"),
			"created_at": photo.get("created_at"),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error fetching photo: {e}")

@router.get("/stats/count")
async def get_photo_count(
	current_user: str = Depends(get_current_user)
):
	"""
	Get user's photo count and limit info
	"""
	try:
		count = await get_user_photo_count(current_user)
		
		return {
			"user_id": current_user,
			"photo_count": count,
			"max_photos": MAX_PHOTOS_PER_USER,
			"remaining_slots": MAX_PHOTOS_PER_USER - count,
			"can_upload": count < MAX_PHOTOS_PER_USER,
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error getting photo count: {e}")
