from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
	email: EmailStr
	age: Optional[int] = None
	height_cm: Optional[int] = None
	gender: Optional[str] = None
	looking_for: Optional[List[str]] = []
	bio: Optional[str] = None
	traits: Optional[List[str]] = []
	values: Optional[List[str]] = []
	green_flags: Optional[List[str]] = []
	red_flags: Optional[List[str]] = []
	lifestyle: Optional[List[str]] = []
	religion: Optional[str] = None
	politics: Optional[str] = None
	languages: Optional[List[str]] = []
	education: Optional[str] = None
	job_title: Optional[str] = None
	company: Optional[str] = None

class UserUpdate(BaseModel):
	age: Optional[int] = None
	height_cm: Optional[int] = None
	gender: Optional[str] = None
	looking_for: Optional[List[str]] = None
	bio: Optional[str] = None
	traits: Optional[List[str]] = None
	values: Optional[List[str]] = None
	green_flags: Optional[List[str]] = None
	red_flags: Optional[List[str]] = None
	lifestyle: Optional[List[str]] = None
	religion: Optional[str] = None
	politics: Optional[str] = None
	languages: Optional[List[str]] = None
	education: Optional[str] = None
	job_title: Optional[str] = None
	company: Optional[str] = None
	profile_complete: Optional[bool] = None

class UserProfile(BaseModel):
	id: str
	email: str
	age: Optional[int]
	height_cm: Optional[int]
	gender: Optional[str]
	looking_for: List[str]
	bio: Optional[str]
	traits: List[str]
	values: List[str]
	green_flags: List[str]
	red_flags: List[str]
	lifestyle: List[str]
	religion: Optional[str]
	politics: Optional[str]
	languages: List[str]
	education: Optional[str]
	job_title: Optional[str]
	company: Optional[str]
	profile_complete: bool

class UserAnonymous(BaseModel):
	id: str
	traits: List[str]
	values: List[str]

class InterestCategory(BaseModel):
	id: str
	name: str
	category: str
	emoji: Optional[str] = None

class UserInterest(BaseModel):
	id: str
	user_id: str
	interest_id: str
	created_at: datetime

class UserPets(BaseModel):
	has_dogs: bool = False
	has_cats: bool = False
	has_other_pets: bool = False
	other_pets_description: Optional[str] = None
	likes_dogs: bool = True
	likes_cats: bool = True
	wants_pet: bool = False
	pet_allergies: Optional[str] = None

class UserLifestyle(BaseModel):
	smoking: Optional[str] = None
	drinking: Optional[str] = None
	drugs: Optional[str] = None
	sleep_schedule: Optional[str] = None
	diet: Optional[str] = None
	exercise_frequency: Optional[str] = None
	social_lifestyle: Optional[str] = None

class UserGoals(BaseModel):
	wants_kids: Optional[str] = None
	marriage_timeline: Optional[str] = None
	relationship_type: Optional[str] = None
	career_ambition: Optional[str] = None
	travel_frequency: Optional[str] = None
	financial_goals: Optional[str] = None

class UserFilters(BaseModel):
	min_age: int = 18
	max_age: int = 50
	max_distance_km: int = 30
	relationship_types: Optional[List[str]] = []
	preferred_interests: Optional[List[str]] = []
	preferred_goals: Optional[List[str]] = []
	show_only_verified: bool = False
	show_only_with_photo: bool = True

class ProfileCompletion(BaseModel):
	sections_completed: List[str]
	sections_remaining: List[str]
	completion_percentage: int

class MatchResponse(BaseModel):
	id: str
	other_user_id: str
	other_user: UserAnonymous
	compatibility_score: float
	match_percentage: float
	both_revealed: bool
	distance_km: Optional[float] = None
	created_at: datetime

class RevealRequest(BaseModel):
	pass

class RevealStatus(BaseModel):
	match_id: str
	both_revealed: bool
	other_user: Optional[UserProfile] = None
