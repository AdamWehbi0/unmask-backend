import os
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
import jwt
from jwt import PyJWTError
from typing import Optional

security = HTTPBearer()

class HTTPAuthCredentials:
	def __init__(self, scheme: str, credentials: str):
		self.scheme = scheme
		self.credentials = credentials

async def verify_token(credentials: HTTPAuthCredentials = Depends(security)) -> str:
	token = credentials.credentials
	try:
		secret = os.getenv("SUPABASE_KEY")
		payload = jwt.decode(token, secret, algorithms=["HS256"])
		user_id: str = payload.get("sub")
		if user_id is None:
			raise HTTPException(status_code=401, detail="Invalid token")
		return user_id
	except PyJWTError:
		raise HTTPException(status_code=401, detail="Invalid token")
