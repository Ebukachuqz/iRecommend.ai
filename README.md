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
SUPABASE_DB_URL=
GROQ_API_KEY=
HF_TOKEN=
```

Client variable:

```text
STREAMLIT_API_BASE_URL=http://127.0.0.1:8000
```

`SUPABASE_SECRET_KEY` is for backend scripts, services, and the API only. Do not expose it in frontend/client deployments.

`SUPABASE_URL` is the Supabase API URL used by the application. `SUPABASE_DB_URL` is the Postgres connection string used only by migration scripts. Copy it from Supabase Dashboard -> Connect. If Supabase marks the direct connection string as not IPv4 compatible, use the Session Pooler URI instead. A connection timeout from `scripts/check_db_connection.py` usually means the direct IPv6-only database host is unreachable from your current network. Do not expose or commit real database credentials.

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

The preferred migration path is the Python runner. Add `SUPABASE_DB_URL` to `.env`, then check connectivity:

```powershell
python scripts/check_db_connection.py
```

If this command times out and Supabase says the direct connection string is not IPv4 compatible, replace `SUPABASE_DB_URL` with the Session Pooler connection string from Supabase Dashboard -> Connect.

Preview the active migration order without connecting or changing schema:

```powershell
python scripts/run_migrations.py --dry-run
```

Run active stable migrations:

```powershell
python scripts/run_migrations.py
```

Run a specific range:

```powershell
python scripts/run_migrations.py --from 003 --to 005
```

The reset migration is destructive and skipped by default. To run only the reset, you must be explicit:

```powershell
python scripts/run_migrations.py --include-reset --confirm-reset --from 000 --to 000
```

Active stable migrations:

```text
src/db/sql/000_reset_database.sql       optional destructive reset
src/db/sql/001_core_schema.sql          product metadata, reviews, personas
src/db/sql/002_task_a_schema.sql        review simulation storage
src/db/sql/003_task_b_schema.sql        recommendation tables and vector columns
src/db/sql/004_pgvector_functions.sql   pgvector RPC functions
src/db/sql/005_indexes.sql              relational and vector indexes
```

Old development migrations are archived in `src/db/sql/archive/`. Reviewers should use the stable migrations above. If direct DB access is unavailable, run the same SQL files manually in Supabase SQL Editor, using `000_reset_database.sql` only for clean rebuilds.

Supabase remains hosted externally; Docker Compose does not start a local database.

## Data Ingestion

Note: the Hugging Face dataset `McAuley-Lab/Amazon-Reviews-2023` currently uses a dataset loading script. Hugging Face `datasets>=4.0.0` removed loading-script support, so ingestion currently requires `datasets<4.0.0` (see `requirements.txt`).

Validation is practical but evaluation-focused. Reviews must include `user_id`, `parent_asin` or `asin`, `rating`, `title`, and `text`; timestamp, verified purchase, and helpful votes are kept when available but are not required. Product metadata must include `parent_asin`, `title`, a category signal, `description`, `features`, `price`, `average_rating`, `store`, and `details`. `rating_number` is optional by default; pass `--require-rating-number` to drop metadata rows without it.

Preferred rebuild order:

```text
migrations -> ingestion -> create_holdout_split.py -> regenerate personas
```

Quick dry-run test:

```powershell
python scripts/ingest_amazon.py --category All_Beauty --min-reviews 15 --max-users 20 --extra-products 100 --dry-run
```

Normal evaluation rebuild:

```powershell
python scripts/ingest_amazon.py --category All_Beauty --min-reviews 15 --max-users 100 --extra-products 1000 --verify
```

Larger final rebuild:

```powershell
python scripts/ingest_amazon.py --category All_Beauty --min-reviews 15 --max-users 300 --extra-products 5000 --verify
```

Create holdout splits:

```powershell
python scripts/create_holdout_split.py --category All_Beauty
```

Holdout splitting is deterministic and per user. For each category, reviews are filtered through matching `amazon_product_metadata` rows because `amazon_reviews` intentionally has no category column. Each user's reviews are split into approximately 70% `persona_train`, 15% `task_a_holdout`, and 15% `task_b_holdout`; for example, 12 reviews become 8 persona reviews, 2 Task A holdout reviews, and 2 Task B holdout reviews. If a category has already been split, pass `--overwrite` to intentionally re-split it.

## Persona Generation

```powershell
python scripts/regenerate_personas.py --category All_Beauty --limit 10
python scripts/regenerate_personas.py --category All_Beauty --limit 20
python scripts/regenerate_personas.py --category All_Beauty --limit 20 --max-reviews-per-user 10
```

Persona generation uses only `task_split='persona_train'` reviews. It sends at most 10 reviews per user to the LLM by default to keep prompt length manageable; use `--max-reviews-per-user` to override this for experiments. The selected review IDs are stored in `user_personas.source_review_ids` and included in the persona run summary. `task_a_holdout` and `task_b_holdout` reviews are reserved for evaluation and should not be used to build personas. `amazon_reviews` does not have or require a `category` column.

## Finding Test IDs

Check whether a category is ready for Task A / Task B smoke tests:

```powershell
python scripts/check_category_readiness.py --category Health_and_Household
```

List evaluation-friendly users:

```powershell
python scripts/list_eval_users.py --category Health_and_Household --limit 10
python scripts/list_eval_users.py --category Health_and_Household --task task_a --require-persona --limit 10
python scripts/list_eval_users.py --category Health_and_Household --task task_b --require-persona --require-taste-vector --limit 10
```

Pick a user for Task A:

1. Choose a row where `has_persona=true` and `task_a_holdout_count>0`.
2. List their holdout reviews and copy a `review_id` / `parent_asin`:

```powershell
python scripts/list_user_holdouts.py --user-id <USER_ID> --category Health_and_Household
```

Pick a user for Task B:

1. Choose a row where `has_persona=true`, `has_taste_vector=true`, and `task_b_holdout_count>0`.

List embedded products (useful for checking whether semantic retrieval has any catalog):

```powershell
python scripts/list_embedded_products.py --category Health_and_Household --limit 10
```

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

Build taste vectors for a batch of users in a category (from `user_personas`):

```powershell
python scripts/build_user_taste_vectors.py --category Health_and_Household --limit 20
python scripts/build_user_taste_vectors.py --category Electronics --limit 20
python scripts/build_user_taste_vectors.py --category Beauty_and_Personal_Care --limit 20
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

Cold-start requests build a low-confidence starter persona from request/context signals and do not require taste vectors. Cross-domain recommendations are conservative: close beauty/skincare categories stay in-domain, while meaningfully different domains such as beauty -> electronics use transferable values like price sensitivity, quality, reliability, simplicity, durability, and value for money. Multi-turn sessions refine active constraints and exclude products already shown in the same session.

Task B also stores an audit trail for evaluation and debugging. `intent_plans` records the structured reasoning brief produced by the intent planner, `recommendation_candidates` records the retrieved/scored candidate pool with before/after rerank ranks, and `recommendation_runs` stores the final output. Intent and candidate traces are best-effort; a trace insert failure should not block recommendation generation.

Task B also accepts a custom persona JSON through `POST /recommendations/generate`. This supports the direct persona -> recommendations flow. The normalizer supports common fields such as `likes`, `interests`, `preferred_products`, `dislikes`, `avoid`, `concerns`, `values`, `priorities`, `budget`, `tone`, `average_rating`, and category signals. It does not attempt to map every possible arbitrary schema.

## Evaluation

Evaluation uses the same runtime services as the app and writes paper-ready artifacts under `outputs/evaluation/`. Run the pipeline in this order:

```text
migrations -> ingestion -> create_holdout_split.py -> regenerate_personas.py -> embed_products.py -> build_user_taste_vectors.py -> evaluation
```

Task A evaluates review/rating simulation against `task_a_holdout` reviews. It reports MAE, RMSE, rounded exact-rating accuracy, within-1-star accuracy, predicted/true mean rating, optimistic bias, and a user-average-rating baseline from `persona_train` reviews.

```powershell
python scripts/evaluate_task_a.py --category Health_and_Household --limit 20
python scripts/evaluate_task_a.py --category Electronics --limit 20
python scripts/evaluate_task_a.py --category Beauty_and_Personal_Care --limit 20
```

Task B evaluates recommendations against positive `task_b_holdout` reviews (`rating >= 4`) as hidden liked products. It reports HitRate@K, NDCG@K, MRR@K, mean found rank, and a same-category popularity/quality baseline. During evaluation, the recommender still excludes `persona_train` products, but it can consider the hidden `task_b_holdout` product so Hit@K is measurable.

```powershell
python scripts/evaluate_task_b.py --category Health_and_Household --limit 20 --k 10
python scripts/evaluate_task_b.py --category Electronics --limit 20 --k 10
python scripts/evaluate_task_b.py --category Beauty_and_Personal_Care --limit 20 --k 10
```

Run all three working categories:

```powershell
python scripts/evaluate_all.py --categories Health_and_Household Electronics Beauty_and_Personal_Care --limit 20 --k 10
```

Metric meanings: HitRate@K is the fraction of examples where the hidden liked product appears in the top K; NDCG@K rewards hits more when they appear higher in the list; MRR@K averages reciprocal rank; MAE/RMSE measure rating error for Task A. CSV/JSON result files and JSON summaries/manifests in `outputs/evaluation/` are the reproducible artifacts to use in the solution paper.

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

Build the two service images directly:

```powershell
docker build -t irecommend-api -f Dockerfile .
docker build -t irecommend-streamlit -f client/streamlit/Dockerfile client/streamlit
```

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

The Docker entrypoints respect Render's `PORT` environment variable while keeping local defaults of `8000` for FastAPI and `8501` for Streamlit.

## Render Deployment

iRecommend deploys to Render as two separate Docker web services: one FastAPI backend and one Streamlit frontend. Supabase stays external and must already be migrated, populated, and have product embeddings/personas prepared before demo use.

1. Push the repository to GitHub.
2. Create the FastAPI backend service on Render.
   - Runtime: Docker.
   - Dockerfile path: `./Dockerfile`.
   - Docker context: `.`.
   - Health check path: `/health`.
3. Add backend environment variables:

```text
SUPABASE_URL
SUPABASE_PUBLIC_KEY
SUPABASE_SECRET_KEY
GROQ_API_KEY
HF_TOKEN
GROQ_MODEL
```

`GROQ_MODEL` can use the default `qwen/qwen3-32b` unless you intentionally changed models. `SUPABASE_DB_URL` is not needed by the web service unless you plan to run migration scripts manually from that environment, which is not recommended.

4. Test the deployed API:

```text
https://<your-api-service>.onrender.com/health
https://<your-api-service>.onrender.com/ready
https://<your-api-service>.onrender.com/docs
```

5. Create the Streamlit frontend service on Render.
   - Runtime: Docker.
   - Dockerfile path: `./client/streamlit/Dockerfile`.
   - Docker context: `./client/streamlit`.
6. Set the frontend environment variable:

```text
STREAMLIT_API_BASE_URL=https://<your-api-service>.onrender.com
```

7. Open the Streamlit service URL and check the health/readiness cards. Streamlit calls to `/health` or `/ready` can also wake the API after Render Free spin-down.

Render Free services sleep after inactivity. The first request after sleep can be slow while the API or Streamlit container wakes up.

The included `render.yaml` is a convenience blueprint for creating the two Docker web services. You still need to provide real secret values in Render.

Long-running ingestion, embedding, persona generation, taste-vector builds, migration runs, and evaluation scripts should be run locally or in a dedicated job environment, not as Render web services.

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
make check-db
make migrate-dry-run
make migrate
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
