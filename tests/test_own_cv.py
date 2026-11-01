"""Tests for the own-CV router (backend/routers/own_cv.py).

Locks in the core behaviour: the user's own CV is stored as-is, kept separate
from generated CVs, rejected when empty or the wrong file type, and removed
together with its file.
"""
import asyncio
import io
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import Base
from backend.routers import own_cv as oc


def _make_session(tmpdir: Path):
    engine = create_engine(f"sqlite:///{tmpdir / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


class OwnCvRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_dir = oc.OWN_CV_DIR
        oc.OWN_CV_DIR = Path(self.tmp.name) / "own_cv"
        self.session = _make_session(Path(self.tmp.name))
        self.addCleanup(self.session.close)

    def tearDown(self):
        oc.OWN_CV_DIR = self.old_dir

    def _upload(self, content=b"%PDF-1.4 fake", filename="resume.pdf"):
        file = UploadFile(file=io.BytesIO(content), filename=filename)
        return asyncio.run(oc.upload(file=file, db=self.session))

    def test_upload_stores_file_and_row(self):
        record = self._upload()
        self.assertTrue(Path(record.file_path).exists())
        self.assertEqual(record.filename, "resume.pdf")
        self.assertTrue(record.id)
        self.assertTrue(record.file_path.endswith(".pdf"))

    def test_rejects_empty_file(self):
        file = UploadFile(file=io.BytesIO(b""), filename="resume.pdf")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(oc.upload(file=file, db=self.session))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_rejects_disallowed_extension(self):
        file = UploadFile(file=io.BytesIO(b"x"), filename="resume.txt")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(oc.upload(file=file, db=self.session))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_safe_ext(self):
        self.assertEqual(oc._safe_ext("Resume.PDF"), ".pdf")
        self.assertEqual(oc._safe_ext("cv"), "")
        self.assertEqual(oc._safe_ext(None), "")

    def test_list_newest_first_and_delete_removes_file(self):
        a = self._upload(filename="one.pdf")
        b = self._upload(filename="two.pdf")
        listing = oc.list_cvs(db=self.session)
        self.assertEqual([c.filename for c in listing], ["two.pdf", "one.pdf"])

        oc.delete_cv(a.id, db=self.session)
        self.assertFalse(Path(a.file_path).exists())
        remaining = oc.list_cvs(db=self.session)
        self.assertEqual([c.filename for c in remaining], ["two.pdf"])


if __name__ == "__main__":
    unittest.main()
