"""A small factory that builds a full CRUD router for a flat record type.

Used for education, certifications, skills, and languages — all of which are
simple lists of records with the same add / list / edit / delete shape.

Note: this module deliberately does NOT use `from __future__ import annotations`.
FastAPI resolves the request-body model from the live annotation object, and
stringised annotations would make it treat the body as a query parameter.
"""
from typing import Type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, get_db


def make_crud_router(
    *,
    prefix: str,
    tag: str,
    model: Type[Base],
    create_schema,
    out_schema,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("", response_model=list[out_schema])
    def list_items(db: Session = Depends(get_db)):
        return db.scalars(
            select(model).order_by(model.sort_order, model.id)
        ).all()

    @router.post("", response_model=out_schema, status_code=201)
    def create_item(payload: create_schema, db: Session = Depends(get_db)):
        item = model(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @router.put("/{item_id}", response_model=out_schema)
    def update_item(item_id: int, payload: create_schema, db: Session = Depends(get_db)):
        item = db.get(model, item_id)
        if item is None:
            raise HTTPException(404, f"{tag} {item_id} not found")
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return item

    @router.delete("/{item_id}", status_code=204)
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        item = db.get(model, item_id)
        if item is None:
            raise HTTPException(404, f"{tag} {item_id} not found")
        db.delete(item)
        db.commit()

    return router
