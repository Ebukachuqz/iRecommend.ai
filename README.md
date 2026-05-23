# iRecommend

Behaviour-aware LLM agents for review simulation and personalised recommendation.

This repository is being built incrementally from the implementation guide. The current implementation covers the repository scaffold, Supabase configuration, Amazon review ingestion modules, persona generation modules, Pydantic persona validation, database hardening migrations, and Task A review simulation.

## Current Phase

- Repository setup and notebook migration
- Database schema hardening
- Holdout-aware persona regeneration
- Task A review and rating simulation

## Setup

1. Create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and fill in your own keys.
4. Run SQL migrations in `src/db/sql/` in Supabase SQL editor.

Do not commit `.env`.

## Environment

Required variables:

```text
SUPABASE_URL=
SUPABASE_PUBLIC_KEY=
SUPABASE_SECRET_KEY=
GROQ_API_KEY=
```

`SUPABASE_SECRET_KEY` is for backend scripts and services only. Do not expose it in frontend code.

## Task A

Run the simulation results migration before Task A:

```powershell
# Supabase SQL editor
src/db/sql/005_simulation_results.sql
```

CLI examples:

```powershell
python scripts/run_task_a_simulation.py --user-id <USER_ID> --parent-asin <PARENT_ASIN>
python scripts/run_task_a_simulation.py --user-id <USER_ID> --use-holdout
python scripts/run_task_a_simulation.py --user-id <USER_ID> --parent-asin <PARENT_ASIN> --nigerian-mode
python scripts/run_task_a_simulation.py --user-id <USER_ID> --list-unseen --limit 10
```

Every successful simulation is inserted into `simulation_results`.

## Task B

Run the recommendation migrations before Task B:

```powershell
# Supabase SQL editor
src/db/sql/004_pgvector_setup.sql
src/db/sql/006_recommendation_tables.sql
```

Embed products and build taste vectors:

```powershell
python scripts/embed_products.py --limit 100
python scripts/build_user_taste_vectors.py --user-id <USER_ID> --category All_Beauty
```

Run recommendations:

```powershell
python scripts/run_task_b_recommendation.py --user-id <USER_ID> --request "I want something affordable and gentle"
python scripts/run_task_b_recommendation.py --user-id <USER_ID>
python scripts/run_task_b_recommendation.py --cold-start --request "I need affordable skincare for oily skin"
```

Every successful recommendation call inserts a row into `recommendation_runs`.

## FastAPI Backend

Run the API locally:

```powershell
uvicorn app.api.main:app --reload
```

Open API docs at:

```text
http://127.0.0.1:8000/docs
```

Core endpoints:

```text
GET  /health
GET  /ready
GET  /users
GET  /users/{user_id}/persona
GET  /users/{user_id}/unseen-products
POST /reviews/simulate
POST /recommendations/generate
POST /recommendations/cold-start
POST /sessions/{session_id}/message
```
