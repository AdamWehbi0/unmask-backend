"""
Photo Management Service
Handles photo uploads, resizing, storage, and deletion
"""
import os
import io
import hashlib
from datetime import datetime
from typing import Optional, List, Tuple
from PIL import Image
import mimetypes
from supabase_client import get_supabase_client

# Photo size configurations (in pixels)
PHOTO_SIZES = {
	"thumbnail": (200, 200),
	"medium": (600, 600),
	"full": (1200, 1200),
}

# Storage bucket name
STORAGE_BUCKET = "user-photos"

# Max file sizes (in bytes)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_PHOTOS_PER_USER = 20

# Allowed formats
ALLOWED_FORMATS = {"image/jpeg", "image/png", "image/webp"}

async def validate_photo_file(file_data: bytes, content_type: str) -> Tuple[bool, str]:
	"""
	Validate photo file
	
	Args:
		file_data: Raw file bytes
		content_type: MIME type
		
	Returns:
		(is_valid, error_message)
	"""
	# Check file size
	if len(file_data) > MAX_FILE_SIZE:
		return False, f"File too large. Max {MAX_FILE_SIZE / 1024 / 1024}MB allowed"
	
	# Check content type
	if content_type not in ALLOWED_FORMATS:
		return False, f"Invalid format. Allowed: {', '.join(ALLOWED_FORMATS)}"
	
	# Try to open as image
	try:
		img = Image.open(io.BytesIO(file_data))
		img.verify()
		return True, ""
	except Exception as e:
		return False, f"Invalid image file: {str(e)}"

def generate_photo_hash(file_data: bytes) -> str:
	"""Generate SHA256 hash of photo for duplicate detection"""
	return hashlib.sha256(file_data).hexdigest()

def resize_image(
	image_data: bytes,
	size: Tuple[int, int],
	format: str = "JPEG",
	quality: int = 85
) -> bytes:
	"""
	Resize image to specified dimensions
	Maintains aspect ratio and centers image in square
	
	Args:
		image_data: Raw image bytes
		size: Target (width, height)
		format: Output format (JPEG, PNG, WEBP)
		quality: JPEG quality (0-100)
		
	Returns:
		Resized image bytes
	"""
	try:
		img = Image.open(io.BytesIO(image_data))
		
		# Convert RGBA to RGB if necessary (for JPEG)
		if img.mode in ("RGBA", "LA", "P"):
			background = Image.new("RGB", img.size, (255, 255, 255))
			background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
			img = background
		
		# Calculate dimensions for aspect ratio preservation
		img.thumbnail(size, Image.Resampling.LANCZOS)
		
		# Create new image with target size and paste resized image centered
		new_img = Image.new("RGB", size, (255, 255, 255))
		offset = (
			(size[0] - img.width) // 2,
			(size[1] - img.height) // 2
		)
		new_img.paste(img, offset)
		
		# Save with compression
		output = io.BytesIO()
		save_kwargs = {"format": format}
		
		if format == "JPEG":
			save_kwargs["quality"] = quality
			save_kwargs["optimize"] = True
		elif format == "WEBP":
			save_kwargs["quality"] = quality
		
		new_img.save(output, **save_kwargs)
		return output.getvalue()
	except Exception as e:
		print(f"Error resizing image: {e}")
		raise

async def upload_photo(
	user_id: str,
	file_data: bytes,
	content_type: str,
	is_primary: bool = False
) -> Optional[dict]:
	"""
	Upload and process a photo for user
	
	Args:
		user_id: User uploading photo
		file_data: Raw image bytes
		content_type: MIME type
		is_primary: Set as primary/profile photo
		
	Returns:
		Photo record dict or None on error
	"""
	try:
		supabase = get_supabase_client()
		
		# Validate file
		is_valid, error_msg = await validate_photo_file(file_data, content_type)
		if not is_valid:
			print(f"Photo validation error: {error_msg}")
			return None
		
		# Check user's photo count
		photo_count = supabase.table("photo_uploads").select(
			"id", count="exact"
		).eq("user_id", user_id).eq("deleted_at", None).execute()
		
		if (photo_count.count or 0) >= MAX_PHOTOS_PER_USER:
			print(f"User {user_id} has reached max photos limit")
			return None
		
		# Generate photo hash for duplicate detection
		photo_hash = generate_photo_hash(file_data)
		
		# Check for duplicate
		existing = supabase.table("photo_uploads").select("*").eq(
			"user_id", user_id
		).eq("photo_hash", photo_hash).eq("deleted_at", None).execute()
		
		if existing.data:
			print(f"Photo already uploaded by user {user_id}")
			return None
		
		# Determine file extension
		ext_map = {
			"image/jpeg": "jpg",
			"image/png": "png",
			"image/webp": "webp",
		}
		extension = ext_map.get(content_type, "jpg")
		
		# Generate unique filename
		photo_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + photo_hash[:8]
		base_filename = f"{user_id}/{photo_id}"
		
		# Create resized versions
		resized_versions = {}
		for size_name, dimensions in PHOTO_SIZES.items():
			resized_data = resize_image(file_data, dimensions)
			filename = f"{base_filename}_{size_name}.{extension}"
			
			# Upload to Supabase Storage
			storage_path = f"photos/{filename}"
			
			try:
				supabase.storage.from_(STORAGE_BUCKET).upload(
					storage_path,
					resized_data,
					{"content-type": content_type}
				)
				resized_versions[f"{size_name}_url"] = storage_path
			except Exception as e:
				print(f"Error uploading {size_name} photo: {e}")
				# Continue with other sizes
		
		# Get current photo count to determine order
		current_photos = supabase.table("photo_uploads").select("photo_order").eq(
			"user_id", user_id
		).eq("deleted_at", None).order("photo_order", desc=True).limit(1).execute()
		
		next_order = 1
		if current_photos.data:
			next_order = (current_photos.data[0].get("photo_order") or 0) + 1
		
		# If no primary photo exists, make this one primary
		if is_primary:
			# Clear primary from other photos
			supabase.table("photo_uploads").update({
				"is_primary": False
			}).eq("user_id", user_id).eq("deleted_at", None).execute()
		else:
			# Check if user has any primary photo
			primary_photo = supabase.table("photo_uploads").select("id").eq(
				"user_id", user_id
			).eq("is_primary", True).eq("deleted_at", None).execute()
			
			if not primary_photo.data:
				is_primary = True
		
		# Create photo record in database
		photo_record = {
			"user_id": user_id,
			"photo_hash": photo_hash,
			"storage_path": resized_versions.get("full_url", ""),
			"thumbnail_url": resized_versions.get("thumbnail_url", ""),
			"medium_url": resized_versions.get("medium_url", ""),
			"full_url": resized_versions.get("full_url", ""),
			"photo_order": next_order,
			"is_primary": is_primary,
			"file_size": len(file_data),
			"created_at": datetime.utcnow().isoformat(),
		}
		
		result = supabase.table("photo_uploads").insert(photo_record).execute()
		
		if result.data:
			return result.data[0]
		else:
			print(f"Error inserting photo record")
			return None
	except Exception as e:
		print(f"Error uploading photo: {e}")
		return None

async def delete_photo(photo_id: str, user_id: str) -> bool:
	"""
	Delete a photo and clean up storage
	
	Args:
		photo_id: Photo to delete
		user_id: User who owns photo
		
	Returns:
		Success boolean
	"""
	try:
		supabase = get_supabase_client()
		
		# Get photo record
		photo_result = supabase.table("photo_uploads").select("*").eq(
			"id", photo_id
		).eq("user_id", user_id).execute()
		
		if not photo_result.data:
			return False
		
		photo = photo_result.data[0]
		
		# Soft delete
		supabase.table("photo_uploads").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).eq("id", photo_id).execute()
		
		# Delete from storage
		if photo.get("storage_path"):
			try:
				supabase.storage.from_(STORAGE_BUCKET).remove([photo["storage_path"]])
			except:
				pass  # Storage cleanup is non-critical
		
		# If this was primary, set next photo as primary
		if photo.get("is_primary"):
			next_photo = supabase.table("photo_uploads").select("id").eq(
				"user_id", user_id
			).eq("deleted_at", None).order("photo_order").limit(1).execute()
			
			if next_photo.data:
				supabase.table("photo_uploads").update({
					"is_primary": True
				}).eq("id", next_photo.data[0]["id"]).execute()
		
		return True
	except Exception as e:
		print(f"Error deleting photo: {e}")
		return False

async def reorder_photos(user_id: str, photo_ids: List[str]) -> bool:
	"""
	Reorder user's photos
	
	Args:
		user_id: User whose photos to reorder
		photo_ids: List of photo IDs in desired order
		
	Returns:
		Success boolean
	"""
	try:
		supabase = get_supabase_client()
		
		# Verify all photos belong to user
		for i, photo_id in enumerate(photo_ids):
			result = supabase.table("photo_uploads").select("*").eq(
				"id", photo_id
			).eq("user_id", user_id).execute()
			
			if not result.data:
				return False
			
			# Update order
			supabase.table("photo_uploads").update({
				"photo_order": i + 1
			}).eq("id", photo_id).execute()
		
		return True
	except Exception as e:
		print(f"Error reordering photos: {e}")
		return False

async def get_user_photos(
	user_id: str,
	limit: int = 20,
	offset: int = 0
) -> List[dict]:
	"""
	Get user's photos ordered by photo_order
	
	Args:
		user_id: User whose photos to fetch
		limit: Max number to return
		offset: Pagination offset
		
	Returns:
		List of photo records
	"""
	try:
		supabase = get_supabase_client()
		
		result = supabase.table("photo_uploads").select("*").eq(
			"user_id", user_id
		).eq("deleted_at", None).order("photo_order").range(
			offset, offset + limit - 1
		).execute()
		
		return result.data or []
	except Exception as e:
		print(f"Error fetching photos: {e}")
		return []

async def get_photo_by_id(photo_id: str, user_id: str) -> Optional[dict]:
	"""
	Get specific photo record
	
	Args:
		photo_id: Photo ID
		user_id: User who owns photo
		
	Returns:
		Photo record or None
	"""
	try:
		supabase = get_supabase_client()
		
		result = supabase.table("photo_uploads").select("*").eq(
			"id", photo_id
		).eq("user_id", user_id).eq("deleted_at", None).execute()
		
		return result.data[0] if result.data else None
	except Exception as e:
		print(f"Error fetching photo: {e}")
		return None

async def set_primary_photo(photo_id: str, user_id: str) -> bool:
	"""
	Set a photo as the user's primary/profile photo
	
	Args:
		photo_id: Photo to set as primary
		user_id: User who owns photo
		
	Returns:
		Success boolean
	"""
	try:
		supabase = get_supabase_client()
		
		# Verify photo exists
		photo_result = supabase.table("photo_uploads").select("*").eq(
			"id", photo_id
		).eq("user_id", user_id).eq("deleted_at", None).execute()
		
		if not photo_result.data:
			return False
		
		# Clear primary from other photos
		supabase.table("photo_uploads").update({
			"is_primary": False
		}).eq("user_id", user_id).eq("deleted_at", None).execute()
		
		# Set as primary
		supabase.table("photo_uploads").update({
			"is_primary": True
		}).eq("id", photo_id).execute()
		
		return True
	except Exception as e:
		print(f"Error setting primary photo: {e}")
		return False

async def get_user_photo_count(user_id: str) -> int:
	"""Get count of user's non-deleted photos"""
	try:
		supabase = get_supabase_client()
		
		result = supabase.table("photo_uploads").select(
			"id", count="exact"
		).eq("user_id", user_id).eq("deleted_at", None).execute()
		
		return result.count or 0
	except Exception as e:
		print(f"Error getting photo count: {e}")
		return 0
