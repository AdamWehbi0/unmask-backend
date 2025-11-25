from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from supabase_client import get_supabase_client
from supabase import Client
import uuid
from typing import Optional, List

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str
    age: int
    gender: str
    location: Optional[str] = None
    interests: List[str] = []
    bio: Optional[str] = None
    height_cm: Optional[int] = None
    looking_for: List[str] = []
    traits: List[str] = []
    values: List[str] = []
    green_flags: List[str] = []
    red_flags: List[str] = []
    religion: Optional[str] = None
    politics: Optional[str] = None
    languages: List[str] = []
    education: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None


class SignupResponse(BaseModel):
    id: str
    email: str
    message: str


@router.post("/signup", response_model=SignupResponse)
async def signup(request: SignupRequest):
    """Sign up a new user"""
    try:
        import hashlib
        
        supabase: Client = get_supabase_client()
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        
        # Normalize gender to lowercase
        gender_map = {
            'M': 'male',
            'F': 'female',
            'NB': 'non_binary',
            'PNTS': 'prefer_not_to_say',
            'male': 'male',
            'female': 'female',
            'non_binary': 'non_binary',
            'prefer_not_to_say': 'prefer_not_to_say'
        }
        normalized_gender = gender_map.get(request.gender, request.gender.lower())
        
        # Create entry in users table with all profile data
        result = supabase.table("users").insert({
            "id": user_id,
            "email": request.email,
            "password_hash": password_hash,
            "name": request.name,
            "bio": request.bio,
            "height_cm": request.height_cm,
            "gender": normalized_gender,
            "looking_for": request.looking_for,
            "age": request.age,
            "traits": request.traits,
            "values": request.values,
            "green_flags": request.green_flags,
            "red_flags": request.red_flags,
            "religion": request.religion,
            "politics": request.politics,
            "languages": request.languages,
            "education": request.education,
            "job_title": request.job_title,
            "company": request.company,
            "profile_complete": False
        }).execute()
        
        return SignupResponse(
            id=user_id,
            email=request.email,
            message="User created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Email already registered")
        if "check" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Invalid input")
        raise HTTPException(status_code=400, detail="Signup failed")


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with email and password"""
    supabase: Client = get_supabase_client()
    
    try:
        import hashlib
        import jwt
        from datetime import datetime, timedelta
        
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        
        # Get user from database
        result = supabase.table("users").select("*").eq("email", request.email).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user = result.data[0]
        
        # Verify password
        if user.get("password_hash") != password_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create JWT token
        payload = {
            "user_id": user["id"],
            "email": user["email"],
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        token = jwt.encode(payload, "your-secret-key", algorithm="HS256")
        
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user_id=user["id"],
            email=user["email"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg.lower():
            raise HTTPException(status_code=500, detail="Database not initialized. Please create tables from schema.sql")
        raise HTTPException(status_code=401, detail="Invalid credentials")
