# Setup

This document covers local setup, environment variables, and Supabase connection configuration.

---

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your own keys. Do not commit `.env`.

Root backend dependencies live in `requirements.txt`. The Streamlit client has its own minimal dependencies in `client/streamlit/requirements.txt`.

---

## Environment Variables

### Backend

```text
SUPABASE_URL=
SUPABASE_PUBLIC_KEY=
SUPABASE_SECRET_KEY=
SUPABASE_DB_URL=
GROQ_API_KEY=
HF_TOKEN=
```

### Client

```text
STREAMLIT_API_BASE_URL=http://127.0.0.1:8000
```

### Variable Reference

| Variable | Used by | Notes |
|---|---|---|
| `SUPABASE_URL` | App and API | Supabase project API URL |
| `SUPABASE_PUBLIC_KEY` | App and API | Anon/public key |
| `SUPABASE_SECRET_KEY` | Backend scripts and API only | Never expose in frontend or client |
| `SUPABASE_DB_URL` | Migration scripts only | Postgres connection string |
| `GROQ_API_KEY` | LLM calls | Groq inference API key |
| `HF_TOKEN` | Ingestion | Hugging Face access token |
| `STREAMLIT_API_BASE_URL` | Streamlit client only | URL of the running FastAPI backend |

> **Warning:** Never expose `SUPABASE_SECRET_KEY` or commit real credentials to version control.

---

## Supabase Connection String

`SUPABASE_DB_URL` is the Postgres connection string used only by migration scripts. Copy it from Supabase Dashboard -> Connect.

If Supabase marks the direct connection string as not IPv4 compatible, use the Session Pooler URI instead. A connection timeout from `scripts/check_db_connection.py` usually means the direct IPv6-only database host is unreachable from your current network.

Check connectivity:

```powershell
python scripts/check_db_connection.py
```

---

## Optional: GROQ_MODEL

The API uses `qwen/qwen3-32b` by default. To override the model without code changes, set:

```text
GROQ_MODEL=qwen/qwen3-32b
```

Leave unset to use the hardcoded default.
