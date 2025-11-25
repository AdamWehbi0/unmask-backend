"""
GDPR Compliance Router
Handles data export, hard deletion, and account deactivation
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from datetime import datetime, timedelta
import json
import csv
import io
import hashlib
from typing import Optional
from supabase_client import get_supabase_client

router = APIRouter(prefix="/gdpr", tags=["GDPR"])

DELETION_WAIT_DAYS = 30

async def get_current_user() -> str:
	"""Placeholder for auth - replace with real auth dependency"""
	return "user-id"

@router.post("/data-export/{user_id}")
async def request_data_export(
	user_id: str,
	export_format: str = "json",  # json or csv
	current_user: str = Depends(get_current_user)
):
	"""
	Request GDPR data export
	User can request all their data in JSON or CSV format
	"""
	if user_id != current_user:
		raise HTTPException(status_code=403, detail="Can only export your own data")
	
	if export_format not in ["json", "csv"]:
		raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
	
	try:
		supabase = get_supabase_client()
		
		# Check if export already requested in last 24 hours
		recent_export = supabase.table("data_exports").select("*").eq(
			"user_id", user_id
		).gte(
			"created_at", 
			(datetime.utcnow() - timedelta(hours=24)).isoformat()
		).eq("status", "pending").execute()
		
		if recent_export.data:
			raise HTTPException(
				status_code=429,
				detail="Data export already requested. Please wait 24 hours before requesting again."
			)
		
		# Create export request
		export_record = {
			"user_id": user_id,
			"export_format": export_format,
			"status": "pending",
			"created_at": datetime.utcnow().isoformat(),
			"expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
		}
		
		result = supabase.table("data_exports").insert(export_record).execute()
		export_id = result.data[0]["id"]
		
		# In production, trigger background job to generate export
		# For now, we queue it
		
		return {
			"export_id": export_id,
			"status": "pending",
			"message": "Data export request received. You will receive a download link via email within 24 hours.",
			"expires_at": export_record["expires_at"],
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error requesting data export: {e}")

@router.get("/data-export/{export_id}/download")
async def download_data_export(
	export_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Download previously requested data export
	Link is valid for 7 days
	"""
	try:
		supabase = get_supabase_client()
		
		# Get export record
		result = supabase.table("data_exports").select("*").eq("id", export_id).execute()
		
		if not result.data:
			raise HTTPException(status_code=404, detail="Export not found")
		
		export = result.data[0]
		
		if export["user_id"] != current_user:
			raise HTTPException(status_code=403, detail="Can only download your own export")
		
		if export["status"] != "completed":
			raise HTTPException(status_code=400, detail=f"Export status: {export['status']}")
		
		if datetime.fromisoformat(export["expires_at"]) < datetime.utcnow():
			raise HTTPException(status_code=410, detail="Export link has expired")
		
		# In production, download from Supabase Storage
		# For now, return mock data
		return {
			"message": "Download link would be provided here",
			"storage_path": export.get("storage_path"),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error downloading export: {e}")

@router.post("/account/deactivate/{user_id}")
async def deactivate_account(
	user_id: str,
	reason: Optional[str] = None,
	current_user: str = Depends(get_current_user)
):
	"""
	Deactivate account (reversible)
	User can reactivate within a certain period
	"""
	if user_id != current_user:
		raise HTTPException(status_code=403, detail="Can only deactivate your own account")
	
	try:
		supabase = get_supabase_client()
		
		# Update account status
		supabase.table("account_status").update({
			"deactivated_at": datetime.utcnow().isoformat(),
			"deactivation_reason": reason,
		}).eq("user_id", user_id).execute()
		
		# Update user status
		supabase.table("users").update({
			"status": "deactivated"
		}).eq("id", user_id).execute()
		
		return {
			"status": "deactivated",
			"message": "Your account has been deactivated. You can reactivate it anytime by logging in.",
			"deactivated_at": datetime.utcnow().isoformat(),
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error deactivating account: {e}")

@router.post("/account/reactivate/{user_id}")
async def reactivate_account(
	user_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Reactivate a deactivated account
	"""
	if user_id != current_user:
		raise HTTPException(status_code=403, detail="Can only reactivate your own account")
	
	try:
		supabase = get_supabase_client()
		
		# Check if account is deactivated
		result = supabase.table("account_status").select("*").eq("user_id", user_id).execute()
		
		if not result.data or not result.data[0].get("deactivated_at"):
			raise HTTPException(status_code=400, detail="Account is not deactivated")
		
		# Update account status
		supabase.table("account_status").update({
			"deactivated_at": None,
		}).eq("user_id", user_id).execute()
		
		# Update user status
		supabase.table("users").update({
			"status": "active"
		}).eq("id", user_id).execute()
		
		return {
			"status": "active",
			"message": "Your account has been reactivated.",
			"reactivated_at": datetime.utcnow().isoformat(),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error reactivating account: {e}")

@router.post("/account/delete-scheduled/{user_id}")
async def request_permanent_deletion(
	user_id: str,
	password: str,
	current_user: str = Depends(get_current_user),
	background_tasks: BackgroundTasks = None
):
	"""
	Request permanent account deletion
	Deletion is scheduled for 30 days from now (gives user time to cancel)
	During this period, all PII is anonymized but account is not fully deleted
	"""
	if user_id != current_user:
		raise HTTPException(status_code=403, detail="Can only delete your own account")
	
	try:
		supabase = get_supabase_client()
		
		# Verify password (simplified - use real auth system)
		user_result = supabase.table("users").select("*").eq("id", user_id).execute()
		if not user_result.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		# Check if deletion already requested
		existing = supabase.table("account_status").select("*").eq(
			"user_id", user_id
		).execute()
		
		if existing.data and existing.data[0].get("deletion_requested_at"):
			raise HTTPException(
				status_code=400,
				detail="Deletion already requested. Check your email for confirmation link."
			)
		
		# Schedule deletion for 30 days from now
		deletion_scheduled_for = datetime.utcnow() + timedelta(days=DELETION_WAIT_DAYS)
		
		supabase.table("account_status").update({
			"deletion_requested_at": datetime.utcnow().isoformat(),
			"deletion_scheduled_for": deletion_scheduled_for.isoformat(),
		}).eq("user_id", user_id).execute()
		
		# Schedule anonymization background task
		if background_tasks:
			background_tasks.add_task(anonymize_user_pii, user_id)
		
		return {
			"status": "deletion_scheduled",
			"message": f"Your account will be permanently deleted on {deletion_scheduled_for.date()}. "
					  "You can cancel this request anytime by logging in.",
			"deletion_scheduled_for": deletion_scheduled_for.isoformat(),
			"days_until_deletion": DELETION_WAIT_DAYS,
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error requesting deletion: {e}")

@router.post("/account/cancel-deletion/{user_id}")
async def cancel_permanent_deletion(
	user_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Cancel a scheduled permanent deletion
	"""
	if user_id != current_user:
		raise HTTPException(status_code=403, detail="Can only cancel your own deletion")
	
	try:
		supabase = get_supabase_client()
		
		# Check if deletion is scheduled
		result = supabase.table("account_status").select("*").eq("user_id", user_id).execute()
		
		if not result.data or not result.data[0].get("deletion_scheduled_for"):
			raise HTTPException(status_code=400, detail="No deletion scheduled")
		
		# Cancel deletion
		supabase.table("account_status").update({
			"deletion_requested_at": None,
			"deletion_scheduled_for": None,
		}).eq("user_id", user_id).execute()
		
		return {
			"status": "deletion_cancelled",
			"message": "Your account deletion has been cancelled.",
			"cancelled_at": datetime.utcnow().isoformat(),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error cancelling deletion: {e}")

async def anonymize_user_pii(user_id: str):
	"""
	Background task: Anonymize all PII for a user scheduled for deletion
	Called immediately when deletion is requested, before the 30-day wait
	"""
	try:
		supabase = get_supabase_client()
		
		# Get user data before anonymization (for audit log)
		user = supabase.table("users").select("*").eq("id", user_id).execute()
		if not user.data:
			return
		
		old_user = user.data[0]
		
		# Anonymize user profile
		anonymous_hash = hashlib.sha256(f"{user_id}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:10]
		
		supabase.table("users").update({
			"name": f"deleted_user_{anonymous_hash}",
			"email": f"deleted_{anonymous_hash}@anonymous.local",
			"phone_number": None,
			"bio": None,
			"job_title": None,
			"company": None,
			"education": None,
			"location": None,
			"latitude": None,
			"longitude": None,
		}).eq("id", user_id).execute()
		
		# Anonymize messages
		supabase.table("messages").update({
			"content": "[deleted]",
		}).eq("sender_id", user_id).execute()
		
		# Delete photos
		photos = supabase.table("photo_uploads").select("id").eq("user_id", user_id).execute()
		for photo in photos.data or []:
			supabase.table("photo_uploads").delete().eq("id", photo["id"]).execute()
		
		# Log anonymization to audit trail
		for field_name in ["name", "email", "phone_number", "bio", "job_title", "company", "education", "location"]:
			old_value = str(old_user.get(field_name, ""))
			old_value_hash = hashlib.sha256(old_value.encode()).hexdigest()
			
			supabase.table("deletion_audit_log").insert({
				"user_id": user_id,
				"field_name": field_name,
				"old_value_hash": old_value_hash,
				"reason": "GDPR deletion requested",
				"anonymized_at": datetime.utcnow().isoformat(),
			}).execute()
		
		print(f"✅ Anonymized PII for user {user_id}")
	except Exception as e:
		print(f"❌ Error anonymizing user {user_id}: {e}")

async def permanently_delete_user(user_id: str):
	"""
	Background task: Permanently delete user account after 30-day window
	Should be called by a scheduled job after DELETION_WAIT_DAYS
	"""
	try:
		supabase = get_supabase_client()
		
		# Check if deletion should proceed
		result = supabase.table("account_status").select("*").eq("user_id", user_id).execute()
		
		if not result.data:
			return
		
		account_status = result.data[0]
		deletion_scheduled_for = datetime.fromisoformat(account_status.get("deletion_scheduled_for", "2099-01-01"))
		
		if datetime.utcnow() < deletion_scheduled_for:
			return  # Not yet time to delete
		
		# Hard delete user and all related data
		supabase.table("users").delete().eq("id", user_id).execute()
		supabase.table("messages").delete().eq("sender_id", user_id).execute()
		supabase.table("messages").delete().eq("recipient_id", user_id).execute()
		supabase.table("matches").delete().eq("user_id_1", user_id).execute()
		supabase.table("matches").delete().eq("user_id_2", user_id).execute()
		supabase.table("blocks").delete().eq("blocker_id", user_id).execute()
		supabase.table("actions").delete().eq("user_id", user_id).execute()
		supabase.table("account_status").delete().eq("user_id", user_id).execute()
		
		# Log final deletion
		supabase.table("deletion_audit_log").insert({
			"user_id": user_id,
			"field_name": "account",
			"old_value_hash": "HARD_DELETED",
			"reason": "GDPR hard deletion after 30-day period",
			"anonymized_at": datetime.utcnow().isoformat(),
		}).execute()
		
		print(f"✅ Permanently deleted account for user {user_id}")
	except Exception as e:
		print(f"❌ Error permanently deleting user {user_id}: {e}")
