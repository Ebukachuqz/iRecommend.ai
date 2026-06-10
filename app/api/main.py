from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health, personas, recommend, sessions, simulate
from app.saas.routes import dashboard as saas_dashboard
from app.saas.routes import organisations as saas_organisations
from app.saas.routes import uploads as saas_uploads


app = FastAPI(
    title="iRecommend API",
    description="Behaviour-aware LLM agents for review simulation and personalised recommendation.",
    version="0.1.0",
)

# Local-development default. Restrict allowed origins before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(personas.router)
app.include_router(simulate.router)
app.include_router(recommend.router)
app.include_router(sessions.router)
app.include_router(saas_organisations.router)
app.include_router(saas_uploads.router)
app.include_router(saas_dashboard.router)
