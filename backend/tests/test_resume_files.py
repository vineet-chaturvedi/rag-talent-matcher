"""Resume files through the app: upload, delete, the duplicate race, and moving files to a bucket."""
import hashlib
import uuid

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Employee, Resume
from app.db.session import SessionLocal
from app.services.resumes import DuplicateResumeError, add_resume, delete_resume
from app.storage import get_storage

pytestmark = pytest.mark.usefixtures("database")


def pdf(tag: str) -> bytes:
    return b"%PDF-1.7 resume " + tag.encode()


async def _employee() -> Employee:
    async with SessionLocal() as s:
        emp = Employee(employee_code=f"EMP-F{uuid.uuid4().hex[:6]}", full_name="File Person")
        s.add(emp)
        await s.commit()
        return emp


async def test_upload_stores_under_a_key_and_delete_removes_it():
    emp = await _employee()
    async with SessionLocal() as s:
        resume = await add_resume(s, get_settings(), emp, "Résumé of File Person.pdf", pdf("one"))
        key = resume.stored_path
        assert key.startswith(f"{emp.employee_code}/") and key.endswith(".pdf") and "Résumé" not in key
        assert await get_storage().get(key) == pdf("one")
        with pytest.raises(DuplicateResumeError):
            await add_resume(s, get_settings(), emp, "again.pdf", pdf("one"))
        assert await get_storage().exists(key)                  # the refused duplicate didn't remove it
        await delete_resume(s, await s.get(Resume, resume.id))
    assert not await get_storage().exists(key)


async def test_failed_insert_cleans_up_only_its_own_file(monkeypatch):
    """The database refuses the row: the file goes, unless another upload of the same file owns it."""
    emp = await _employee()
    async with SessionLocal() as s:
        original_commit = s.commit

        async def failing_commit():
            raise RuntimeError("database down")
        monkeypatch.setattr(s, "commit", failing_commit)
        with pytest.raises(RuntimeError):
            await add_resume(s, get_settings(), emp, "x.pdf", pdf("lonely"))
        monkeypatch.setattr(s, "commit", original_commit)
    assert not await get_storage().exists(f"{emp.employee_code}/{hashlib.sha256(pdf('lonely')).hexdigest()[:16]}.pdf")


async def test_move_local_files_to_s3(monkeypatch, tmp_path, caplog):
    """(Other tests' resume rows have no files: the tool reports those, so only this resume is checked.)"""
    from moto import mock_aws

    import scripts.migrate_files as mf
    from app.storage import make_storage
    from tests.conftest import make_settings

    caplog.set_level("INFO", logger="migrate_files")
    emp = await _employee()
    async with SessionLocal() as s:
        r = await add_resume(s, get_settings(), emp, "cv.pdf", pdf("to-s3"))
        # a row from before Step 15: the stored path is the local file path itself
        legacy = get_storage().path_of(r.stored_path).as_posix()
        r.stored_path = legacy
        await s.commit()
        rid = r.id
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "t")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "t")
    with mock_aws():
        import boto3
        boto3.client("s3", region_name="eu-west-1").create_bucket(
            Bucket="moved-resumes", CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
        s3 = make_storage(make_settings(storage_backend="s3", s3_bucket="moved-resumes", aws_region="eu-west-1"))
        monkeypatch.setattr("app.storage.get_storage", lambda: s3)
        ours = f"resume {rid} ("
        await mf.migrate(get_settings().upload_dir, dry_run=True)
        assert ours not in caplog.text
        async with SessionLocal() as s:
            assert (await s.get(Resume, rid)).stored_path == legacy          # dry run changed nothing
        await mf.migrate(get_settings().upload_dir, dry_run=False)
        assert ours not in caplog.text
        async with SessionLocal() as s:
            moved = await s.get(Resume, rid)
            assert moved.stored_path == f"{emp.employee_code}/{moved.file_hash[:16]}.pdf"
        assert await s3.get(moved.stored_path) == pdf("to-s3")
        caplog.clear()
        await mf.migrate(get_settings().upload_dir, dry_run=False)               # again: nothing to do
        assert ours not in caplog.text and "0 moved" in caplog.text
        async with SessionLocal() as s:
            rows = (await s.scalars(select(Resume))).all()
        missing = [x for x in rows if not await s3.exists(x.stored_path)]
        # every other resume of this test run is still local: --check would report exactly those
        assert all(x.id != rid for x in missing)
        await s3.close()
