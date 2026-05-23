# iRecommend Streamlit Client

This Streamlit frontend demonstrates iRecommend through the FastAPI backend. It does not call Supabase, Groq, or internal `src` services directly.

## Run

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

## Configuration

Required client variable:

```text
STREAMLIT_API_BASE_URL=http://127.0.0.1:8000
```

The Streamlit client does not need Supabase or Groq secrets.
