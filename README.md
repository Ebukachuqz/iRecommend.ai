# iRecommend

Behaviour-aware LLM agents for review simulation and personalised recommendation.

This repository is being built incrementally from the implementation guide. The current implementation covers the repository scaffold, Supabase configuration, Amazon review ingestion modules, persona generation modules, Pydantic persona validation, and database hardening migrations.

## Current Phase

- Phase 1: repository setup and notebook migration
- Phase 2: database schema hardening
- Holdout-aware persona regeneration foundation from the immediate execution order

## Setup

1. Create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and fill in your own keys.
4. Run SQL migrations in `src/db/sql/` in Supabase SQL editor.

Do not commit `.env`.
