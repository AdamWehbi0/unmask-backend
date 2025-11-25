import os
from typing import Optional

from supabase import create_client, Client

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def masked_key() -> Optional[str]:
    if not SUPABASE_KEY:
        return None
    if len(SUPABASE_KEY) <= 8:
        return "*" * len(SUPABASE_KEY)
    return SUPABASE_KEY[:4] + "..." + SUPABASE_KEY[-4:]
