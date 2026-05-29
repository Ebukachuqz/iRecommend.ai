# Deployment

This document covers Docker, Render, and Makefile deployment for iRecommend.

---

## Docker

### Build Images

Build the two service images directly:

```powershell
docker build -t irecommend-api -f Dockerfile .
docker build -t irecommend-streamlit -f client/streamlit/Dockerfile client/streamlit
```

Or build via Compose:

```powershell
docker compose build
```

### Run Locally

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

### Docker Environment

Docker uses `.env` for the API service. The Streamlit service receives only:

```text
STREAMLIT_API_BASE_URL=http://api:8000
```

The Docker entrypoints respect Render's `PORT` environment variable while keeping local defaults of `8000` for FastAPI and `8501` for Streamlit.

Supabase remains hosted externally. Docker Compose does not start a local database.

---

## Render Deployment

iRecommend deploys to Render as two separate Docker web services: one FastAPI backend and one Streamlit frontend. Supabase must already be migrated, populated, and have product embeddings and personas prepared before demo use.

### FastAPI Backend

1. Push the repository to GitHub.
2. Create a new web service on Render:
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

### Streamlit Frontend

5. Create a second web service on Render:
   - Runtime: Docker.
   - Dockerfile path: `./client/streamlit/Dockerfile`.
   - Docker context: `./client/streamlit`.
6. Set the frontend environment variable:

```text
STREAMLIT_API_BASE_URL=https://<your-api-service>.onrender.com
```

7. Open the Streamlit service URL and check the health/readiness cards. Streamlit calls to `/health` or `/ready` can also wake the API after Render Free spin-down.

### Render Free Tier Note

Render Free services sleep after inactivity. The first request after sleep can be slow while the API or Streamlit container wakes up.

The included `render.yaml` is a convenience blueprint for creating the two Docker web services. You still need to provide real secret values in Render.

### Long-Running Scripts

Long-running ingestion, embedding, persona generation, preference-vector builds, migration runs, and evaluation scripts should be run locally or in a dedicated job environment, not as Render web services.

---

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
make build-preference-vector USER_ID=<USER_ID> CATEGORY=All_Beauty
make check-db
make migrate-dry-run
make migrate
```

On Windows without `make`, run the equivalent commands shown in the relevant docs sections.
