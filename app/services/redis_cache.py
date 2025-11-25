import redis.asyncio as redis
import json
from typing import Any, Optional
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_client: Optional[redis.Redis] = None

async def init_redis():
	"""Initialize Redis connection pool"""
	global redis_client
	try:
		redis_client = await redis.from_url(REDIS_URL, encoding="utf8", decode_responses=True)
		await redis_client.ping()
		print("✅ Redis connected successfully")
	except Exception as e:
		print(f"❌ Redis connection failed: {e}")
		redis_client = None

async def close_redis():
	"""Close Redis connection"""
	global redis_client
	if redis_client:
		await redis_client.close()

def get_redis() -> Optional[redis.Redis]:
	"""Get Redis client instance"""
	return redis_client

async def set_cache(key: str, value: Any, ttl: int = 3600) -> bool:
	"""
	Set value in cache with TTL (default 1 hour)
	
	Args:
		key: Cache key
		value: Value to cache (will be JSON serialized)
		ttl: Time to live in seconds
	"""
	if not redis_client:
		return False
	
	try:
		if isinstance(value, (dict, list)):
			value = json.dumps(value)
		await redis_client.setex(key, ttl, value)
		return True
	except Exception as e:
		print(f"Cache set error: {e}")
		return False

async def get_cache(key: str) -> Optional[Any]:
	"""
	Get value from cache
	
	Args:
		key: Cache key
		
	Returns:
		Cached value or None if not found/expired
	"""
	if not redis_client:
		return None
	
	try:
		value = await redis_client.get(key)
		if value:
			try:
				return json.loads(value)
			except:
				return value
		return None
	except Exception as e:
		print(f"Cache get error: {e}")
		return None

async def delete_cache(key: str) -> bool:
	"""Delete value from cache"""
	if not redis_client:
		return False
	
	try:
		await redis_client.delete(key)
		return True
	except Exception as e:
		print(f"Cache delete error: {e}")
		return False

async def delete_cache_pattern(pattern: str) -> int:
	"""Delete all keys matching pattern (e.g., 'user:123:*')"""
	if not redis_client:
		return 0
	
	try:
		keys = await redis_client.keys(pattern)
		if keys:
			return await redis_client.delete(*keys)
		return 0
	except Exception as e:
		print(f"Cache pattern delete error: {e}")
		return 0

async def increment_counter(key: str, increment: int = 1, ttl: int = 3600) -> int:
	"""Increment counter (for rate limiting, stats)"""
	if not redis_client:
		return 0
	
	try:
		value = await redis_client.incr(key, increment)
		await redis_client.expire(key, ttl)
		return value
	except Exception as e:
		print(f"Counter increment error: {e}")
		return 0

async def cache_exists(key: str) -> bool:
	"""Check if key exists in cache"""
	if not redis_client:
		return False
	
	try:
		return await redis_client.exists(key) > 0
	except Exception as e:
		print(f"Cache exists check error: {e}")
		return False

# Cache key constants
def CACHE_KEY_USER_PROFILE(user_id: str) -> str:
	return f"user:{user_id}:profile"

def CACHE_KEY_DISCOVERY(user_id: str, distance: int) -> str:
	return f"discovery:{user_id}:{distance}"

def CACHE_KEY_USER_MATCHES(user_id: str) -> str:
	return f"matches:{user_id}"

def CACHE_KEY_INTEREST_CATEGORIES() -> str:
	return "interests:categories"

def CACHE_KEY_USER_INTERESTS(user_id: str) -> str:
	return f"user:{user_id}:interests"

def CACHE_KEY_USER_FILTERS(user_id: str) -> str:
	return f"user:{user_id}:filters"

def CACHE_KEY_USER_LOCATION(user_id: str) -> str:
	return f"user:{user_id}:location"

# Cache TTL constants (in seconds)
CACHE_TTL_SHORT = 300  # 5 minutes
CACHE_TTL_MEDIUM = 3600  # 1 hour
CACHE_TTL_LONG = 86400  # 24 hours
