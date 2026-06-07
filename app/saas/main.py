from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.saas.routes import organisations, uploads


app = FastAPI(
    title="iRecommend SaaS API",
    description="Merchant-facing onboarding and customer intelligence APIs.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "irecommend-saas-api"}


app.include_router(organisations.router)
app.include_router(uploads.router)
