from fastapi import Request
from app.services.analytics import log_event
import asyncio

async def analytics_middleware(request: Request, call_next):
	path = request.url.path
	method = request.method
	user_id = getattr(request.state, "user_id", None)
	
	event_type = None
	if "users" in path and method == "POST":
		event_type = "profile_created"
	elif "users" in path and method == "PUT":
		event_type = "profile_updated"
	elif "matches" in path and method == "POST":
		event_type = "match_created"
	elif "swipe" in path and "like" in path and method == "POST":
		event_type = "user_liked"
	elif "block" in path and method == "POST":
		event_type = "user_blocked"
	elif "reports" in path and method == "POST":
		event_type = "abuse_reported"
	elif "messages" in path and method == "POST":
		event_type = "message_sent"
	elif "interests" in path and method == "POST":
		event_type = "interest_added"
	elif "profile" in path and method == "POST":
		event_type = "profile_section_updated"
	elif "recommendations" in path and method == "GET":
		event_type = "recommendations_viewed"
	
	response = await call_next(request)
	
	if event_type and user_id and response.status_code == 200:
		asyncio.create_task(log_event(user_id, event_type, {"path": path, "status": response.status_code}))
	
	return response
