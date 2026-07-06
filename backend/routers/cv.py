"""CV pack generation and download, attached to a job."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..cv_generator import generate_cv
from ..db import get_db
from ..models import CVPack, Job
from ..schemas import CVGenerateRequest, CVPackOut

router = APIRouter(prefix="/api", tags=["cv"])


@router.post("/jobs/{job_id}/cv", response_model=CVPackOut)
def create_cv(job_id: int, payload: CVGenerateRequest, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    result = generate_cv(db, job, payload.answers or {})
    pack = CVPack(
        job_id=job_id,
        file_path=result["file_path"],
        filename=result["filename"],
        target_title=result["target_title"],
        used_ai=result["used_ai"],
        flags=result["flags"],
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return pack


@router.get("/jobs/{job_id}/cv", response_model=list[CVPackOut])
def list_cv(job_id: int, db: Session = Depends(get_db)):
    return (
        db.query(CVPack)
        .filter(CVPack.job_id == job_id)
        .order_by(CVPack.id.desc())
        .all()
    )


@router.get("/cv/{pack_id}/download")
def download_cv(pack_id: int, db: Session = Depends(get_db)):
    pack = db.get(CVPack, pack_id)
    if pack is None:
        raise HTTPException(404, "cv pack not found")
    path = Path(pack.file_path)
    if not path.exists():
        raise HTTPException(410, "the file was moved or deleted — regenerate it")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=pack.filename,
    )
