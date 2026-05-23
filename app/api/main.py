from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health, personas, recommend, sessions, simulate


app = FastAPI(
    title="iRecommend API",
    description="Behaviour-aware LLM agents for review simulation and personalised recommendation.",
    version="0.1.0",
)

# Local-development default. Restrict allowed origins before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(personas.router)
app.include_router(simulate.router)
app.include_router(recommend.router)
app.include_router(sessions.router)
