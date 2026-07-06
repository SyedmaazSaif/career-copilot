"""career-copilot FastAPI backend.

Spawned by Electron as a sidecar on launch and killed on quit. Runs fully
local. No paid API is ever called from here.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import DB_PATH, init_db
from .routers import ai, cv, experiences, importer, jobs, profile, settings
from .routers.flat import (
    certification_router,
    education_router,
    language_router,
    skill_router,
)
from .scheduler import start_scheduler

# Load .env from the career-copilot root (one level up from backend/).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="career-copilot", version="0.0.1")

# The frontend runs on the Vite dev server (5173) in dev and from a file URL
# in the packaged app. Allow both to reach the local backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    start_scheduler()


# Profile CMS routers
app.include_router(profile.router)
app.include_router(experiences.router)
app.include_router(education_router)
app.include_router(certification_router)
app.include_router(skill_router)
app.include_router(language_router)
app.include_router(importer.router)

# Jobs + CRM
app.include_router(jobs.router)
app.include_router(settings.router)
app.include_router(ai.router)
app.include_router(cv.router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "career-copilot",
        "version": app.version,
        "db": DB_PATH.exists(),
        "ollama_enabled": os.getenv("OLLAMA_ENABLED", "false").lower() == "true",
    }
