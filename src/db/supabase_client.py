from functools import lru_cache

from supabase import Client, create_client

from src.config import Settings, get_settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    return create_supabase_client(settings)


def create_supabase_client(settings: Settings) -> Client:
    url, key = settings.require_supabase()
    return create_client(url, key)
