import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase_url: str = os.getenv("SUPABASE_URL", "")
supabase_key: str = os.getenv("SUPABASE_KEY", "")

if not supabase_url or not supabase_key:
    supabase_url = "https://placeholder-project.supabase.co"
    supabase_key = "placeholder-anon-key"

supabase: Client = create_client(supabase_url, supabase_key)

