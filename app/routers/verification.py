from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
from supabase_client import get_supabase_client
from app.auth import verify_token

router = APIRouter(prefix="/verification", tags=["verification"])

class VerificationStatus(BaseModel):
	status: str
	verification_badge: bool
	expires_at: Optional[str] = None

class AdminReviewRequest(BaseModel):
	status: str
	notes: str = ""

@router.post("/upload-id")
async def upload_id(
	file: UploadFile,
	id_type: str,
	user_id: str = Depends(verify_token)
):
	if id_type not in ["passport", "driver_license", "national_id"]:
		raise HTTPException(status_code=400, detail="Invalid ID type")
	
	if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf')):
		raise HTTPException(status_code=400, detail="Invalid file type")
	
	client = get_supabase_client()
	
	try:
		content = await file.read()
		file_path = f"{user_id}/{id_type}_{datetime.utcnow().timestamp()}"
		
		client.storage.from_("id-submissions").upload(
			file_path,
			content,
			{"contentType": file.content_type}
		)
		
		client.table("user_verifications").upsert({
			"user_id": user_id,
			"storage_path": file_path,
			"id_type": id_type,
			"status": "pending"
		}, on_conflict="user_id").execute()
		
		return {"status": "pending", "message": "ID uploaded. Pending manual review."}
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def get_verification_status(user_id: str = Depends(verify_token)):
	client = get_supabase_client()
	try:
		resp = client.table("user_verifications").select("*").eq("user_id", user_id).single().execute()
		data = resp.data
		return VerificationStatus(
			status=data["status"],
			verification_badge=data["status"] == "approved",
			expires_at=data.get("expires_at")
		)
	except Exception:
		return VerificationStatus(status="none", verification_badge=False, expires_at=None)

@router.get("/pending-queue")
async def get_pending_verifications(limit: int = 50, admin_id: str = Depends(verify_token)):
	client = get_supabase_client()
	
	try:
		user = client.table("users").select("is_admin").eq("id", admin_id).single().execute()
		if not user.data.get("is_admin"):
			raise HTTPException(status_code=403, detail="Admin access required")
	except:
		raise HTTPException(status_code=403, detail="Admin access required")
	
	try:
		resp = client.table("user_verifications")\
			.select("id, user_id, id_type, status, created_at")\
			.eq("status", "pending")\
			.order("created_at", desc=True)\
			.limit(limit)\
			.execute()
		return resp.data
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.get("/details/{verification_id}")
async def get_verification_details(verification_id: str, admin_id: str = Depends(verify_token)):
	client = get_supabase_client()
	
	try:
		user = client.table("users").select("is_admin").eq("id", admin_id).single().execute()
		if not user.data.get("is_admin"):
			raise HTTPException(status_code=403, detail="Admin access required")
	except:
		raise HTTPException(status_code=403, detail="Admin access required")
	
	try:
		resp = client.table("user_verifications").select("*").eq("id", verification_id).single().execute()
		data = resp.data
		
		storage_url = None
		if data.get("storage_path"):
			try:
				storage_url = client.storage.from_("id-submissions").create_signed_url(data["storage_path"], 3600)
			except:
				pass
		
		return {**data, "storage_url": storage_url}
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))

@router.post("/review/{verification_id}")
async def review_verification(
	verification_id: str,
	review: AdminReviewRequest,
	admin_id: str = Depends(verify_token)
):
	if review.status not in ["approved", "rejected"]:
		raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")
	
	client = get_supabase_client()
	
	try:
		user = client.table("users").select("is_admin").eq("id", admin_id).single().execute()
		if not user.data.get("is_admin"):
			raise HTTPException(status_code=403, detail="Admin access required")
	except:
		raise HTTPException(status_code=403, detail="Admin access required")
	
	try:
		verification = client.table("user_verifications").select("*").eq("id", verification_id).single().execute()
		if not verification.data:
			raise HTTPException(status_code=404, detail="Verification not found")
		
		user_id = verification.data["user_id"]
		update_data = {"status": review.status, "updated_at": datetime.utcnow().isoformat()}
		
		if review.status == "approved":
			update_data["verified_at"] = datetime.utcnow().isoformat()
			update_data["expires_at"] = (datetime.utcnow() + timedelta(days=365)).isoformat()
			client.table("users").update({"is_verified": True, "verification_badge": True}).eq("id", user_id).execute()
		elif review.status == "rejected":
			update_data["rejection_reason"] = review.notes
		
		client.table("user_verifications").update(update_data).eq("id", verification_id).execute()
		
		return {"status": review.status, "message": f"Verification {review.status}", "notes": review.notes}
	except Exception as e:
		raise HTTPException(status_code=400, detail=str(e))
