"""Keep the user's own resume file, separate from the generated CVs.

The file is stored as-is and never parsed into the profile. The apply window's
Attach CV button reveals this file first; when none is uploaded it falls back to
the job's generated CV.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import DATA_DIR, get_db
from ..models import UploadedCv
from ..schemas import UploadedCvOut

router = APIRouter(prefix="/api/own-cv", tags=["own-cv"])

OWN_CV_DIR = DATA_DIR / "own_cv"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXT = {".pdf", ".docx", ".doc"}


def _safe_ext(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


@router.post("", response_model=UploadedCvOut)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Store the user's own CV file. Kept as-is; never applied to the profile."""
    content = await file.read()
    if not content:
        raise HTTPException(422, "empty file")
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "file too large (max 10 MB)")
    ext = _safe_ext(file.filename)
    if ext not in ALLOWED_EXT:
        raise HTTPException(422, "please upload a PDF or Word document (.pdf, .docx, .doc)")

    OWN_CV_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"my_cv_{uuid.uuid4().hex[:12]}{ext}"
    dest = OWN_CV_DIR / stem
    dest.write_bytes(content)

    record = UploadedCv(
        filename=(file.filename or f"resume{ext}").strip() or f"resume{ext}",
        file_path=str(dest),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[UploadedCvOut])
def list_cvs(db: Session = Depends(get_db)):
    """Uploaded CVs, newest first."""
    return db.query(UploadedCv).order_by(UploadedCv.id.desc()).all()


@router.delete("/{cv_id}")
def delete_cv(cv_id: int, db: Session = Depends(get_db)):
    """Remove an uploaded CV and its file."""
    record = db.get(UploadedCv, cv_id)
    if record is None:
        raise HTTPException(404, "not found")
    path = Path(record.file_path)
    db.delete(record)
    db.commit()
    try:
        if path.exists():
            path.unlink()
    except OSError:
        # The record is gone either way; an unremovable file must not block it.
        pass
    return {"ok": True}


@router.get("/{cv_id}/download")
def download_cv(cv_id: int, db: Session = Depends(get_db)):
    record = db.get(UploadedCv, cv_id)
    if record is None:
        raise HTTPException(404, "not found")
    path = Path(record.file_path)
    if not path.exists():
        raise HTTPException(410, "the file was moved or deleted — upload it again")
    return FileResponse(str(path), filename=record.filename)
