"""AI-assisted features: resume parsing, CV generation, provider config.

The provider is chosen in Settings (Ollama, free and local, or an
OpenAI-compatible API like DeepSeek with the user's own key). Every consumer
falls back to deterministic logic when no AI is available, so the app never
hard-requires a paid API.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import deepseek_client, envfile, hardware, llm, ollama_setup, resume as resume_mod
from ..db import get_db
from ..schemas import (
    AiConfigIn,
    ImportResult,
    OllamaSetupRequest,
    ResumeApplyRequest,
    ResumeParseResult,
)
from .importer import apply_profile_data

router = APIRouter(prefix="/api/ai", tags=["ai"])

MAX_RESUME_BYTES = 8 * 1024 * 1024  # 8 MB


@router.get("/status")
def ai_status():
    """The active AI provider and whether it is ready."""
    return llm.status()


@router.get("/config")
def ai_config():
    """The provider settings the user can edit (never the API key itself)."""
    return {
        "provider": llm.provider(),
        "model": deepseek_client.model() if llm.provider() != "ollama" else "",
        "base_url": deepseek_client.base_url() if llm.provider() != "ollama" else "",
        "has_key": bool(deepseek_client.api_key()),
    }


@router.put("/config")
def save_ai_config(payload: AiConfigIn):
    """Save the provider choice (non-secret). The API key is handled by
    Electron's safeStorage, never sent here or written to disk."""
    provider = (payload.provider or "ollama").strip().lower()
    if provider not in ("ollama", "deepseek", "custom"):
        raise HTTPException(422, "provider must be ollama, deepseek or custom")

    values = {"AI_PROVIDER": provider}
    if provider != "ollama":
        model = (payload.model or "").strip()
        base = (payload.base_url or "").strip()
        if provider == "deepseek":
            model = model or "deepseek-chat"
            base = base or "https://api.deepseek.com"
        if not model:
            raise HTTPException(422, "a model name is required")
        if not base.startswith("http"):
            raise HTTPException(422, "the base URL must start with http")
        values["AI_MODEL"] = model
        values["AI_BASE_URL"] = base.rstrip("/")

    envfile.set_values(values)
    return ai_config()


@router.get("/hardware")
def hardware_check():
    """This machine's specs and the largest local model it can actually run.
    The UI shows this before installing anything, so the choice is informed
    rather than a 4 GB download that turns out to be unusable."""
    return hardware.recommend()


@router.post("/ollama/setup")
def start_ollama_setup(payload: OllamaSetupRequest | None = None):
    """One-click: install Ollama (Windows), download the model, and turn it on.
    Defaults to the hardware-recommended model; `model` overrides it."""
    return ollama_setup.start_setup(payload.model if payload else None)


@router.get("/ollama/setup/status")
def ollama_setup_status():
    return {"running": ollama_setup.is_running(), **ollama_setup.status()}


@router.post("/resume/parse", response_model=ResumeParseResult)
async def parse_resume(file: UploadFile = File(...)):
    """Read an uploaded resume (PDF/DOCX/TXT) into profile data for preview."""
    content = await file.read()
    if not content:
        raise HTTPException(422, "empty file")
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(413, "file too large (max 8 MB)")
    text = resume_mod.extract_text(file.filename or "", content)
    if not text.strip():
        raise HTTPException(
            422, "couldn't read any text from that file (is it a scanned image?)"
        )
    data, used_ai, error = resume_mod.parse_resume(text)
    return ResumeParseResult(data=data, used_ai=used_ai, error=error)


@router.post("/resume/apply", response_model=ImportResult)
def apply_resume(payload: ResumeApplyRequest, db: Session = Depends(get_db)):
    """Write reviewed resume data into the profile (replaces existing records)."""
    if not isinstance(payload.data, dict):
        raise HTTPException(422, "data must be an object")
    return apply_profile_data(db, payload.data, replace=payload.replace)
