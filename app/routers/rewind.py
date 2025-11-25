"""
Rewind Feature Router
Allows users to undo their last action (swipe, match, etc.)
Premium feature with limited uses
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import Optional
from supabase_client import get_supabase_client

router = APIRouter(prefix="/rewind", tags=["Rewind"])

REWIND_LIMIT_FREE = 0  # Free users can't rewind
REWIND_LIMIT_PREMIUM = 5  # Premium users get 5 rewinds per month

async def get_current_user() -> str:
	"""Placeholder for auth - replace with real auth dependency"""
	return "user-id"

@router.get("/remaining/{user_id}")
async def get_remaining_rewinds(
	user_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Get number of remaining rewinds for user
	"""
	if user_id != current_user:
		raise HTTPException(status_code=403, detail="Can only check your own rewinds")
	
	try:
		supabase = get_supabase_client()
		
		# Get user subscription level
		user_result = supabase.table("users").select("subscription_level").eq("id", user_id).execute()
		if not user_result.data:
			raise HTTPException(status_code=404, detail="User not found")
		
		subscription_level = user_result.data[0].get("subscription_level", "free")
		
		# Get remaining rewinds from user_rewinds table
		rewinds = supabase.table("user_rewinds").select(
			"id",
			count="exact"
		).eq("user_id", user_id).eq("status", "available").execute()
		
		remaining = rewinds.count or 0
		
		# Determine max based on subscription
		if subscription_level == "premium":
			max_rewinds = REWIND_LIMIT_PREMIUM
		else:
			max_rewinds = REWIND_LIMIT_FREE
		
		return {
			"user_id": user_id,
			"subscription_level": subscription_level,
			"remaining_rewinds": remaining,
			"max_rewinds": max_rewinds,
			"can_rewind": remaining > 0,
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error getting remaining rewinds: {e}")

@router.post("/action/{action_id}")
async def rewind_action(
	action_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Undo the last action
	Restores the profile to discovery feed
	Only works for swipes, not matches or messages
	"""
	try:
		supabase = get_supabase_client()
		
		# Get the action
		action_result = supabase.table("actions").select("*").eq("id", action_id).execute()
		if not action_result.data:
			raise HTTPException(status_code=404, detail="Action not found")
		
		action = action_result.data[0]
		
		if action["user_id"] != current_user:
			raise HTTPException(status_code=403, detail="Can only rewind your own actions")
		
		# Only allow rewinding swipes
		if action["action_type"] not in ["swipe_left", "swipe_right"]:
			raise HTTPException(status_code=400, detail=f"Cannot rewind {action['action_type']} actions")
		
		# Check if action is recent (within 24 hours)
		action_time = datetime.fromisoformat(action["created_at"])
		if (datetime.utcnow() - action_time).days > 1:
			raise HTTPException(status_code=400, detail="Can only rewind actions within 24 hours")
		
		# Check if already rewound
		existing_rewind = supabase.table("user_rewinds").select("*").eq(
			"action_id", action_id
		).execute()
		
		if existing_rewind.data:
			raise HTTPException(status_code=400, detail="This action has already been rewound")
		
		# Check remaining rewinds
		rewinds_result = supabase.table("user_rewinds").select(
			"id",
			count="exact"
		).eq("user_id", current_user).eq("status", "available").execute()
		
		remaining = rewinds_result.count or 0
		if remaining <= 0:
			raise HTTPException(status_code=429, detail="No rewinds remaining")
		
		# Mark action as deleted (soft delete)
		supabase.table("actions").update({
			"deleted_at": datetime.utcnow().isoformat()
		}).eq("id", action_id).execute()
		
		# If it was a swipe_right, undo the match/like
		if action["action_type"] == "swipe_right":
			target_user = action.get("target_user_id")
			
			# Check if a match was created
			match_result = supabase.table("matches").select("*").eq(
				"user_id_1", current_user
			).eq("user_id_2", target_user).execute()
			
			if match_result.data:
				match = match_result.data[0]
				
				# If mutual match, downgrade to one-sided like
				if match.get("status") == "matched":
					supabase.table("matches").update({
						"status": "liked",
						"liked_by_id": target_user,  # Only liked by the other person now
						"updated_at": datetime.utcnow().isoformat()
					}).eq("id", match["id"]).execute()
				else:
					# Just delete the like
					supabase.table("matches").delete().eq("id", match["id"]).execute()
		
		# Record the rewind
		rewind_record = {
			"user_id": current_user,
			"action_id": action_id,
			"rewound_action_type": action["action_type"],
			"rewound_target_user_id": action.get("target_user_id"),
			"rewound_at": datetime.utcnow().isoformat(),
			"status": "used",
		}
		
		supabase.table("user_rewinds").insert(rewind_record).execute()
		
		# Decrement available rewinds
		available_rewinds = supabase.table("user_rewinds").select("id").eq(
			"user_id", current_user
		).eq("status", "available").execute()
		
		new_remaining = (available_rewinds.count or 0) - 1
		
		return {
			"status": "success",
			"message": f"Action rewound successfully. {new_remaining} rewinds remaining.",
			"action_id": action_id,
			"rewound_action_type": action["action_type"],
			"remaining_rewinds": new_remaining,
			"rewound_at": datetime.utcnow().isoformat(),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error rewinding action: {e}")

@router.post("/restore-profile/{profile_id}")
async def restore_profile_to_discovery(
	profile_id: str,
	current_user: str = Depends(get_current_user)
):
	"""
	Restore a profile back to the discovery feed after rewinding a swipe
	This endpoint is called after a successful rewind to show the profile again
	"""
	try:
		supabase = get_supabase_client()
		
		# Verify the profile exists
		profile_result = supabase.table("users").select("*").eq("id", profile_id).eq(
			"deleted_at", None
		).execute()
		
		if not profile_result.data:
			raise HTTPException(status_code=404, detail="Profile not found")
		
		# In practice, this would be handled by the discovery algorithm
		# The profile is automatically eligible again since the action was deleted
		
		return {
			"status": "restored",
			"message": f"Profile {profile_id} has been restored to your discovery feed",
			"restored_at": datetime.utcnow().isoformat(),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error restoring profile: {e}")

@router.get("/history")
async def get_rewind_history(
	current_user: str = Depends(get_current_user),
	limit: int = 20,
	offset: int = 0
):
	"""
	Get user's rewind history
	Shows what actions have been rewound
	"""
	try:
		supabase = get_supabase_client()
		
		# Get rewind history
		result = supabase.table("user_rewinds").select(
			"*",
		).eq("user_id", current_user).eq("status", "used").order(
			"rewound_at", desc=True
		).range(offset, offset + limit - 1).execute()
		
		rewinds = result.data or []
		
		# Enrich with action details
		enriched = []
		for rewind in rewinds:
			enriched.append({
				"rewind_id": rewind["id"],
				"action_type": rewind["rewound_action_type"],
				"target_user_id": rewind["rewound_target_user_id"],
				"rewound_at": rewind["rewound_at"],
			})
		
		return {
			"user_id": current_user,
			"rewind_history": enriched,
			"count": len(enriched),
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error getting rewind history: {e}")
