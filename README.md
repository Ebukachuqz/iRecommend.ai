# iRecommend.ai

**Behaviour-aware LLM agents for review simulation and personalised recommendation.**

iRecommend is a behaviour-aware LLM agent system that does two things:

- **Task A — Review Simulation:** Given a user persona and a product, predict what rating the user would give and generate a realistic simulated review.
- **Task B — Personalised Recommendation:** Given a user persona and a free-text request, retrieve, score, and rerank products into a personalised recommendation list with transparent scoring and evidence.

The core insight is that structured user personas, extracted from Amazon review history via LLM, can drive both tasks. The system learns how a user writes, what they value, how strictly they rate, and what they avoid, then uses that understanding to simulate behaviour or generate recommendations.

**Key design principles:**

- Persona-grounded: every decision traces back to the user's persona.
- Transparent scoring: all recommendation scores are broken down (semantic similarity, preference match, product quality, price fit, popularity).
- Hybrid statistical + LLM: ratings blend statistical prediction with LLM prediction via calibrated weighting.
- Multi-source retrieval: Task B combines six retrieval sources (preference vectors, query vectors, collaborative filtering, bought-together, attribute matching, quality fallback).
- Evaluation-first: built-in holdout splitting, metrics computation, and baseline comparisons.

---

## Contents

- [Architecture](#architecture)
- [Quick Setup](#quick-setup)
- [Environment Variables](#environment-variables)
- [Pipeline Overview](#pipeline-overview)
- [Command Cheat Sheet](#command-cheat-sheet)
- [API and Client](#api-and-client)
- [Evaluation](#evaluation)
- [MVP Demo Flow](#mvp-demo-flow)
- [Known Limitations](#known-limitations)
- [Documentation](#documentation)

---

## Architecture

```text
Amazon Reviews 2023
-> Supabase reviews + product metadata
-> holdout split
-> persona generation
-> product embeddings + preference vectors
-> Task A review simulation
-> Task B recommendation
-> FastAPI backend
-> Streamlit client
```

Supabase is the hosted system of record. Product embeddings use pgvector in Supabase. The Streamlit client talks to FastAPI over HTTP only.

---

## Quick Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your own keys. Do not commit `.env`.

See [docs/SETUP.md](docs/SETUP.md) for full environment variable reference and Supabase connection guidance.

---

## Environment Variables

**Backend:**

```text
SUPABASE_URL
SUPABASE_PUBLIC_KEY
SUPABASE_SECRET_KEY
SUPABASE_DB_URL
GROQ_API_KEY
HF_TOKEN
```

**Client:**

```text
STREAMLIT_API_BASE_URL=http://127.0.0.1:8000
```

> **Warning:** Never expose `SUPABASE_SECRET_KEY` or commit real credentials to version control.

---

## Pipeline Overview

Run steps in this order for a full rebuild:

| Step | Script | Docs |
|---|---|---|
| 1. Migrations | `run_migrations.py` | [docs/DATABASE_MIGRATIONS.md](docs/DATABASE_MIGRATIONS.md) |
| 2. Ingestion | `ingest_amazon.py` | [docs/INGESTION.md](docs/INGESTION.md) |
| 3. Holdout split | `create_holdout_split.py` | [docs/INGESTION.md](docs/INGESTION.md) |
| 4. Personas | `generate_personas.py` | [docs/PERSONAS.md](docs/PERSONAS.md) |
| 5. Product embeddings | `embed_products.py` | [docs/TASK_B.md](docs/TASK_B.md) |
| 6. Preference vectors | `build_user_preference_vectors.py` | [docs/TASK_B.md](docs/TASK_B.md) |
| 7. Task A batch | `run_task_a_batch.py` | [docs/TASK_A.md](docs/TASK_A.md) |
| 8. Evaluation | `run_evaluation.py` | [EVALUATION.md](EVALUATION.md) |

---

## Command Cheat Sheet

**Migrations:**
```powershell
python scripts/run_migrations.py --dry-run
python scripts/run_migrations.py
```

**Ingestion:**
```powershell
python scripts/ingest_amazon.py --category Health_and_Household --min-reviews 15 --max-users 200 --extra-products 150 --verify
```

**Holdout split:**
```powershell
python scripts/create_holdout_split.py --category Health_and_Household
```

**Personas:**
```powershell
python scripts/generate_personas.py --category Health_and_Household --limit 20
```

**Product embeddings:**
```powershell
python scripts/embed_products.py --category Health_and_Household --limit 100
```

**Preference vectors:**
```powershell
python scripts/build_user_preference_vectors.py --category Health_and_Household --limit 20
```

**Task A batch:**
```powershell
python scripts/run_task_a_batch.py --category Health_and_Household --limit 50
```

**Evaluation:**
```powershell
python scripts/run_evaluation.py --task both --categories Health_and_Household Electronics Beauty_and_Personal_Care --task-a-limit 50 --task-b-limit 100 --max-holdouts-per-user 2 --k 10 --force-rerun
```

**API:**
```powershell
uvicorn app.api.main:app --reload
```

**Streamlit:**
```powershell
streamlit run client/streamlit/streamlit_app.py
```

---

## API and Client

Start the FastAPI backend:

```powershell
uvicorn app.api.main:app --reload
```

Interactive docs: `http://127.0.0.1:8000/docs`

Start the Streamlit client:

```powershell
streamlit run client/streamlit/streamlit_app.py
```

Open: `http://localhost:8501`

The Streamlit client only needs `STREAMLIT_API_BASE_URL`. It does not need Supabase, Groq, or Hugging Face credentials.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for Docker and Render deployment instructions.

---

## Evaluation

Evaluation is fully implemented and writes paper-ready artifacts to `outputs/evaluation/`.

- Task A evaluates review and rating simulation against `task_a_holdout` reviews, reporting MAE, RMSE, exact accuracy, within-1-star accuracy, and a user-average baseline.
- Task B evaluates recommendation against positive `task_b_holdout` reviews, reporting HitRate@K, NDCG@K, MRR@K, and a popularity baseline.

See [EVALUATION.md](EVALUATION.md) for the full evaluation methodology, metrics, DCR-inspired diagnostics, interpretation, and limitations.

---

## MVP Demo Flow

1. Start FastAPI.
2. Start Streamlit.
3. Load a user persona.
4. Simulate a review for an unseen product.
5. Generate personalised recommendations.
6. Try cold-start recommendations.
7. Try custom JSON mode in Review Simulation.
8. Try custom persona mode in Recommendations.

---

## Known Limitations

- Supabase must already be configured and migrated before the app is usable.
- Product embeddings and personas must be prepared before meaningful recommendations are possible.
- Broader baselines and ablations are future work.
- Evaluation has been implemented; see [EVALUATION.md](EVALUATION.md).
- The Next.js frontend under `client/nextjs` is reserved for future work.

---

## Documentation

- [Setup](docs/SETUP.md)
- [Database migrations](docs/DATABASE_MIGRATIONS.md)
- [Data ingestion](docs/INGESTION.md)
- [Persona generation](docs/PERSONAS.md)
- [Task A review simulation](docs/TASK_A.md)
- [Task B recommendation](docs/TASK_B.md)
- [Evaluation report](EVALUATION.md)
- [Deployment](docs/DEPLOYMENT.md)
