from __future__ import annotations

from supabase import Client

from src.config import Settings, get_settings
from src.db.supabase_client import get_supabase_client


def get_app_settings() -> Settings:
    return get_settings()


def get_db_client() -> Client:
    return get_supabase_client()
