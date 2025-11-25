from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from supabase_client import get_supabase_client

scheduler = BackgroundScheduler()

def recompute_match_scores():
	try:
		client = get_supabase_client()
		matches = client.table("matches").select("id").is_("deleted_at", None).execute()
		
		for match in matches.data:
			client.table("matches").update({
				"updated_at": datetime.utcnow().isoformat()
			}).eq("id", match["id"]).execute()
	except Exception as e:
		print(f"Error in recompute_match_scores: {e}")

def cleanup_expired_verifications():
	try:
		client = get_supabase_client()
		cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
		
		expired = client.table("user_verifications").select("id").lt("created_at", cutoff_date).eq("status", "pending").is_("deleted_at", None).execute()
		
		for verification in expired.data:
			client.table("user_verifications").update({
				"deleted_at": datetime.utcnow().isoformat()
			}).eq("id", verification["id"]).execute()
	except Exception as e:
		print(f"Error in cleanup_expired_verifications: {e}")

def generate_daily_analytics():
	try:
		client = get_supabase_client()
		today = datetime.utcnow().date().isoformat()
		
		daily_signups = client.table("users").select("id").gte("created_at", today).is_("deleted_at", None).execute()
		daily_matches = client.table("matches").select("id").gte("created_at", today).is_("deleted_at", None).execute()
		
		client.table("analytics_events").insert({
			"event_type": "daily_summary",
			"event_data": {
				"date": today,
				"new_signups": len(daily_signups.data),
				"new_matches": len(daily_matches.data)
			}
		}).execute()
	except Exception as e:
		print(f"Error in generate_daily_analytics: {e}")

def start_background_jobs():
	scheduler.add_job(recompute_match_scores, 'interval', hours=1)
	scheduler.add_job(cleanup_expired_verifications, 'interval', hours=24)
	scheduler.add_job(generate_daily_analytics, 'cron', hour=0, minute=0)
	scheduler.start()

def stop_background_jobs():
	scheduler.shutdown()
