from supabase_client import get_supabase_client
from datetime import datetime

async def log_event(user_id: str, event_type: str, event_data: dict = None):
	try:
		client = get_supabase_client()
		client.table("analytics_events").insert({
			"user_id": user_id,
			"event_type": event_type,
			"event_data": event_data or {},
			"created_at": datetime.utcnow().isoformat()
		}).execute()
	except Exception as e:
		print(f"Error logging event: {e}")
