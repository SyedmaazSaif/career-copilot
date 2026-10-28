"""Cover letter and screener-answer endpoints, attached to a job."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import cover_letter
from ..db import get_db
from ..models import Job

router = APIRouter(prefix="/api/jobs", tags=["cover-letter"])


@router.post("/{job_id}/cover-letter")
def create_cover_letter(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return cover_letter.generate_cover_letter(db, job)


@router.get("/{job_id}/screener")
def get_screener_answers(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return cover_letter.screener_answers(db)
