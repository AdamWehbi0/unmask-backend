import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from migrations import run_migrations
from supabase_client import get_supabase_client, masked_key
from app.routers import matches, reveal, locations, verification, messages, discovery, blocks, reports, swipe, notifications, premium, admin, webhooks, interests, profile, recommendations, gdpr, rewind, photos
from app.middleware.rate_limiter import rate_limit_middleware
from app.middleware.analytics_middleware import analytics_middleware
from app.services.jobs import start_background_jobs, stop_background_jobs
from app.services.redis_cache import init_redis, close_redis

app = FastAPI(title="unmask-backend")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.middleware("http")(analytics_middleware)
app.middleware("http")(rate_limit_middleware)

@app.on_event("startup")
async def startup():
	run_migrations()
	await init_redis()
	
	fcm_path = os.getenv("FCM_CREDENTIALS_PATH")
	if not fcm_path:
		raise RuntimeError("FCM_CREDENTIALS_PATH environment variable not set. Please configure Firebase credentials.")
	if not os.path.exists(fcm_path):
		raise RuntimeError(f"Firebase credentials file not found at {fcm_path}. Please ensure FCM_CREDENTIALS_PATH points to a valid file.")
	
	start_background_jobs()

@app.on_event("shutdown")
async def shutdown():
	await close_redis()
	stop_background_jobs()

app.include_router(matches.router)
app.include_router(reveal.router)
app.include_router(locations.router)
app.include_router(verification.router)
app.include_router(messages.router)
app.include_router(discovery.router)
app.include_router(blocks.router)
app.include_router(reports.router)
app.include_router(swipe.router)
app.include_router(notifications.router)
app.include_router(premium.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
app.include_router(interests.router)
app.include_router(profile.router)
app.include_router(recommendations.router)
app.include_router(gdpr.router)
app.include_router(rewind.router)
app.include_router(photos.router)

@app.get("/health")
def health():
	return {"status": "ok"}

@app.get("/supabase-info")
def supabase_info(check: bool = False):
	url = os.getenv("SUPABASE_URL")
	key = masked_key()
	if not url or not key:
		return {"configured": False, "SUPABASE_URL": url, "SUPABASE_KEY": key}

	if not check:
		return {"configured": True, "SUPABASE_URL": url, "SUPABASE_KEY": key}

	try:
		client = get_supabase_client()
		return {"configured": True, "SUPABASE_URL": url, "SUPABASE_KEY": key, "check": "client-created"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Supabase check failed: {e}")


if __name__ == "__main__":
	import uvicorn

	uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
