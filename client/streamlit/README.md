# iRecommend Streamlit Client

This Streamlit frontend demonstrates iRecommend through the FastAPI backend. It does not call Supabase, Groq, Hugging Face, or internal `src` services directly.

It can be moved into a separate repository later because its only runtime contract is the FastAPI HTTP API.

## Run From The Main Repo

Start the backend first:

```powershell
uvicorn app.api.main:app --reload
```

Then run Streamlit:

```powershell
streamlit run client/streamlit/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

## Run As A Detached Client

From the repository root:

```powershell
cd client/streamlit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run streamlit_app.py
```

The backend API must be running separately:

```powershell
uvicorn app.api.main:app --reload
```

## Configuration

Required client variable:

```text
STREAMLIT_API_BASE_URL=http://127.0.0.1:8000
```

The Streamlit client does not need Supabase, Groq, or Hugging Face secrets.

## Demo Modes

Persona Explorer, Review Simulation, Recommendations, and Cold Start use the FastAPI backend over HTTP.

Review Simulation supports:

- existing user mode: select a Supabase-backed user and unseen product
- custom JSON mode: paste a persona-like JSON object and product-like JSON object

Recommendations supports:

- existing user mode: generate recommendations for a stored persona
- custom persona mode: paste a persona-like JSON object and request

Custom JSON support is bounded. The backend normalizes common field variants such as `likes`, `dislikes`, `budget`, `tone`, `average_rating`, `name`, `category`, and `reviews_count`, but it does not claim to understand every arbitrary schema.

## Docker

From the repository root, run both API and Streamlit:

```powershell
docker compose up
```

The Streamlit container receives:

```text
STREAMLIT_API_BASE_URL=http://api:8000
```

It does not receive backend secrets.
