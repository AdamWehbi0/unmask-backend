from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import time
from typing import Dict, Tuple

rate_limit_store: Dict[str, list] = {}

LIMITS = {
	"swipe": (100, 3600),
	"message": (60, 3600),
	"block": (20, 3600),
	"report": (10, 86400),
	"global_ip": (1000, 3600)
}

def get_rate_limit_key(request: Request, action: str) -> str:
	if action in ["swipe", "message", "block", "report"]:
		user_id = getattr(request.state, "user_id", None)
		if user_id:
			return f"{action}:{user_id}"
	
	client_ip = request.client.host if request.client else "unknown"
	return f"global_ip:{client_ip}"

async def rate_limit_middleware(request: Request, call_next):
	path = request.url.path
	method = request.method
	
	action = None
	if "swipe" in path and method == "POST":
		action = "swipe"
	elif "messages" in path and method == "POST":
		action = "message"
	elif "block" in path and method == "POST":
		action = "block"
	elif "reports" in path and method == "POST":
		action = "report"
	
	if action:
		key = get_rate_limit_key(request, action)
		limit, window = LIMITS[action]
		
		now = time.time()
		
		if key not in rate_limit_store:
			rate_limit_store[key] = []
		
		rate_limit_store[key] = [ts for ts in rate_limit_store[key] if now - ts < window]
		
		if len(rate_limit_store[key]) >= limit:
			retry_after = int(window - (now - rate_limit_store[key][0]))
			raise HTTPException(
				status_code=429,
				detail=f"Rate limit exceeded for {action}",
				headers={"Retry-After": str(retry_after)}
			)
		
		rate_limit_store[key].append(now)
	
	response = await call_next(request)
	return response
