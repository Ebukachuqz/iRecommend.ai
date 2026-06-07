from __future__ import annotations

from supabase import Client

from src.db.supabase_client import get_supabase_client


def get_saas_client() -> Client:
    """Return the shared Supabase client for SaaS routes."""

    return get_supabase_client()
