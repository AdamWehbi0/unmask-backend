from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Optional
from app.auth import verify_token
from supabase_client import get_supabase_client
from datetime import datetime
from pydantic import BaseModel

class ReportRequest(BaseModel):
	reported_user_id: str
	reason: str
	details: Optional[str] = None

class AdminReviewRequest(BaseModel):
	action: str
	notes: Optional[str] = None

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("")
async def create_report(
	report: ReportRequest,
	user_id: str = Depends(verify_token)
):
	if user_id == report.reported_user_id:
		raise HTTPException(status_code=400, detail="Cannot report yourself")
	
	client = get_supabase_client()
	
	valid_reasons = ['inappropriate_profile', 'harassing_messages', 'bot_account', 'catfish', 'explicit_content', 'scam', 'other']
	if report.reason not in valid_reasons:
		raise HTTPException(status_code=400, detail=f"Invalid reason. Must be one of: {valid_reasons}")
	
	try:
		reported_user = client.table("users").select("id").eq("id", report.reported_user_id).is_("deleted_at", None).single().execute()
		if not reported_user.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		existing = client.table("abuse_reports").select("id").eq("reporter_id", user_id).eq("reported_id", report.reported_user_id).is_("deleted_at", None).single().execute()
		if existing.data:
			raise HTTPException(status_code=409, detail="You have already reported this user")
		
		resp = client.table("abuse_reports").insert({
			"reporter_id": user_id,
			"reported_id": report.reported_user_id,
			"reason": report.reason,
			"details": report.details,
			"status": "pending"
		}).select().execute()
		
		return resp.data[0]
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/pending", tags=["admin"])
async def get_pending_reports(
	admin_id: str = Depends(verify_token),
	limit: int = Query(50, ge=1, le=100),
	offset: int = Query(0, ge=0)
):
	client = get_supabase_client()
	
	try:
		admin = client.table("users").select("is_admin").eq("id", admin_id).single().execute()
		if not admin.data or not admin.data.get("is_admin"):
			raise HTTPException(status_code=403, detail="Admin access required")
		
		reports = client.table("abuse_reports").select(
			"id, reporter_id, reported_id, reason, details, status, created_at, abuse_reports.users(email)"
		).eq("status", "pending").is_("deleted_at", None).order("created_at", desc=False).execute()
		
		total = len(reports.data)
		paginated = reports.data[offset:offset + limit]
		
		return {
			"data": paginated,
			"total": total,
			"limit": limit,
			"offset": offset
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/{report_id}", tags=["admin"])
async def get_report_details(
	report_id: str,
	admin_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		admin = client.table("users").select("is_admin").eq("id", admin_id).single().execute()
		if not admin.data or not admin.data.get("is_admin"):
			raise HTTPException(status_code=403, detail="Admin access required")
		
		report = client.table("abuse_reports").select("*").eq("id", report_id).is_("deleted_at", None).single().execute()
		if not report.data:
			raise HTTPException(status_code=404, detail="Report not found")
		
		return report.data
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/{report_id}/resolve", tags=["admin"])
async def resolve_report(
	report_id: str,
	review: AdminReviewRequest,
	admin_id: str = Depends(verify_token)
):
	client = get_supabase_client()
	
	try:
		admin = client.table("users").select("is_admin").eq("id", admin_id).single().execute()
		if not admin.data or not admin.data.get("is_admin"):
			raise HTTPException(status_code=403, detail="Admin access required")
		
		report = client.table("abuse_reports").select("reported_id").eq("id", report_id).is_("deleted_at", None).single().execute()
		if not report.data:
			raise HTTPException(status_code=404, detail="Report not found")
		
		client.table("abuse_reports").update({
			"status": "resolved",
			"reviewed_by": admin_id,
			"resolution_notes": review.notes,
			"updated_at": datetime.utcnow().isoformat()
		}).eq("id", report_id).execute()
		
		if review.action == "suspend":
			reported_user_id = report.data["reported_id"]
			user_report_count = client.table("abuse_reports").select("id").eq("reported_id", reported_user_id).eq("status", "resolved").execute()
			
			if len(user_report_count.data) >= 3:
				client.table("users").update({"deleted_at": datetime.utcnow().isoformat()}).eq("id", reported_user_id).execute()
				return {"status": "resolved", "action": "user_suspended"}
		
		return {"status": "resolved"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
