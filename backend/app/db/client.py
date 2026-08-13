import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase_url: str = os.getenv("SUPABASE_URL", "")
supabase_key: str = os.getenv("SUPABASE_KEY", "")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

supabase: Client = create_client(supabase_url, supabase_key)
