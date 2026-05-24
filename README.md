# iRecommend

Behaviour-aware LLM agents for review simulation and personalised recommendation.

iRecommend learns structured personas from Amazon review history, uses those personas to simulate future reviews, and generates personalised recommendations with transparent scoring and evidence.

## Architecture

```text
Amazon Reviews 2023
-> Supabase reviews + product metadata
-> holdout split
-> persona generation
-> Task A review simulation
-> Task B recommendation
-> FastAPI backend
-> Streamlit client
```

Supabase is the hosted system of record. Product embeddings use pgvector in Supabase. The Streamlit client talks to FastAPI over HTTP only.

## Environment

Backend variables:

```text
SUPABASE_URL=
SUPABASE_PUBLIC_KEY=
SUPABASE_SECRET_KEY=
GROQ_API_KEY=
HF_TOKEN=
```

Client variable:

```text
STREAMLIT_API_BASE_URL=http://127.0.0.1:8000
```

`SUPABASE_SECRET_KEY` is for backend scripts, services, and the API only. Do not expose it in frontend/client deployments.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your own keys. Do not commit `.env`.

Root backend dependencies live in `requirements.txt`. The detachable Streamlit client has its own minimal dependencies in `client/streamlit/requirements.txt`.

## Supabase SQL Migrations

Run these in the Supabase SQL editor:

```text
src/db/sql/001_initial_schema.sql
src/db/sql/002_persona_schema_update.sql
src/db/sql/003_holdout_split.sql
src/db/sql/004_pgvector_setup.sql
src/db/sql/005_simulation_results.sql
src/db/sql/006_recommendation_tables.sql
src/db/sql/007_task_b_upgrade.sql
```

Supabase remains hosted externally; Docker Compose does not start a local database.

## Data Ingestion

```powershell
python scripts/ingest_amazon.py --category All_Beauty
```

Create holdout splits:

```powershell
python scripts/create_holdout_split.py --category All_Beauty
```

## Persona Generation

```powershell
python scripts/regenerate_personas.py --category All_Beauty --limit 10
```

Persona generation uses only `task_split='persona_train'` reviews. `amazon_reviews` does not have or require a `category` column.

## Task A

Run review simulation:

```powershell
python scripts/run_task_a_simulation.py --user-id <USER_ID> --parent-asin <PARENT_ASIN>
python scripts/run_task_a_simulation.py --user-id <USER_ID> --use-holdout
python scripts/run_task_a_simulation.py --user-id <USER_ID> --parent-asin <PARENT_ASIN> --nigerian-mode
```

Successful simulations are stored in `simulation_results`.

Task A also accepts custom persona and product JSON through `POST /reviews/simulate`. This satisfies the direct persona + product -> review/rating flow. The backend normalizes common field variants, preserves unknown persona fields under `extra_persona_signals.unmapped_fields`, preserves unknown product fields under `details.custom_fields`, and rejects only inputs that are too empty to support the task.

## Task B

Embed products:

```powershell
python scripts/embed_products.py --limit 100
python scripts/embed_products.py --category All_Beauty --limit 100 --dry-run
python scripts/embed_products.py --category All_Beauty --force-reembed
```

Product embeddings are built from rich product metadata: title, category path, features, description, brand/store, price tier, and useful details. The exact raw price is not embedded; the script uses semantic tiers such as `budget`, `mid-range`, `premium`, and `luxury` because those meanings are more stable than a changing seller price. The text used for each embedding is stored in `product_embeddings.product_text` for debugging and reproducibility. Re-run with `--force-reembed` when the product text strategy changes.

Build a user taste vector:

```powershell
python scripts/build_user_taste_vectors.py --user-id <USER_ID> --category All_Beauty
```

Taste vectors are category-specific and unit-normalized after averaging liked product embeddings. They are built from rating >= 4 `persona_train` reviews whose products match the requested metadata category.

Run recommendations:

```powershell
python scripts/run_task_b_recommendation.py --user-id <USER_ID> --request "I want something affordable and gentle"
python scripts/run_task_b_recommendation.py --cold-start --request "I need affordable skincare for oily skin"
```

FastAPI and CLI callers use the Task B service layer, and `service.recommend()` now wraps the explicit LangGraph workflow for intent planning, retrieval, scoring, reranking, session update, and storage.

Successful recommendation calls are stored in `recommendation_runs`.

Task B retrieves candidates from multiple sources before scoring: taste-vector semantic search, request-query semantic search, collaborative signals from similar users' taste vectors, persona/intent attribute matching, and a quality/popularity fallback. Collaborative filtering is only one signal; the system goes beyond it by grounding retrieval, scoring, and final reasons in the user's persona and request intent. Cold-start and custom-persona requests still work through request-query retrieval and quality fallback when no stored taste vector exists.

Task B also stores an audit trail for evaluation and debugging. `intent_plans` records the structured reasoning brief produced by the intent planner, `recommendation_candidates` records the retrieved/scored candidate pool with before/after rerank ranks, and `recommendation_runs` stores the final output. Intent and candidate traces are best-effort; a trace insert failure should not block recommendation generation.

Task B also accepts a custom persona JSON through `POST /recommendations/generate`. This supports the direct persona -> recommendations flow. The normalizer supports common fields such as `likes`, `interests`, `preferred_products`, `dislikes`, `avoid`, `concerns`, `values`, `priorities`, `budget`, `tone`, `average_rating`, and category signals. It does not attempt to map every possible arbitrary schema.

## FastAPI Backend

```powershell
uvicorn app.api.main:app --reload
```

API docs:

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

## Streamlit Client

Run from the root environment:

```powershell
streamlit run client/streamlit/streamlit_app.py
```

Run independently:

```powershell
cd client/streamlit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run streamlit_app.py
```

Open:

```text
http://localhost:8501
```

The Streamlit client only needs `STREAMLIT_API_BASE_URL`. It does not need Supabase, Groq, or Hugging Face secrets.

`client/nextjs` is reserved for a later polished frontend. It is not implemented yet.

## Docker

Build images:

```powershell
docker compose build
```

Run API and Streamlit:

```powershell
docker compose up
```

Open:

```text
FastAPI:   http://127.0.0.1:8000/docs
Streamlit: http://127.0.0.1:8501
```

Stop:

```powershell
docker compose down
```

Docker uses `.env` for the API service. The Streamlit service receives only:

```text
STREAMLIT_API_BASE_URL=http://api:8000
```

## Makefile

```powershell
make install
make test
make run-api
make run-streamlit
make docker-build
make docker-up
make docker-down
make embed-products LIMIT=100
make build-taste-vector USER_ID=<USER_ID> CATEGORY=All_Beauty
```

On Windows without `make`, run the equivalent commands shown in the sections above.

## MVP Demo Flow

1. Start the API.
2. Start Streamlit.
3. Load a user persona.
4. Simulate a review for an unseen product.
5. Generate personalised recommendations.
6. Try cold-start recommendations.
7. Try custom JSON mode in Review Simulation with a persona and product.
8. Try custom persona mode in Recommendations.

## Known Limitations

- Supabase must already be configured and migrated.
- Product embeddings must be built before semantic Task B retrieval is useful.
- Cross-platform user history agents are postponed.
- Baselines, ablations, and evaluation reports are planned later.
- Docker Compose does not provide a local Supabase/Postgres instance.

## Next Planned Work

- Docker/reproducibility polish follow-ups if needed.
- Research baselines and ablations.
- Evaluation scripts and reporting.
- Optional Next.js frontend under `client/nextjs`.
