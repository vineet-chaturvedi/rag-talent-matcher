"""
The database layer on SQLite AND PostgreSQL (run the suite once per database, see tests/conftest.py):
migrations, no drift between models and migrations, upgrading a pre-migration database, keyword search,
the vector store, the text-length guard and UTC times.
"""
import uuid

import pytest
from sqlalchemy import select, text

from app.db.enums import ChunkSection, ResumeStatus
from app.db.models import Employee, Experience, Resume, ResumeChunk
from app.db.session import BASELINE_REVISION as BASELINE
from app.db.session import IS_POSTGRES, SessionLocal, alembic_config
from app.rag.keyword_index import ensure_keyword_index, keyword_search, replace_resume_rows

pytestmark = pytest.mark.usefixtures("database")


async def _resume(code: str, chunks: list[str]) -> tuple[int, int]:
    """An employee with a READY resume and these chunk texts (in resume_chunks and the keyword index)."""
    async with SessionLocal() as s:
        emp = Employee(employee_code=code, full_name=f"Person {code}")
        s.add(emp)
        await s.flush()
        res = Resume(employee_id=emp.id, original_filename="cv.pdf", stored_path=f"{code}/cv.pdf",
                     file_hash=uuid.uuid4().hex + uuid.uuid4().hex, mime_type="application/pdf",
                     file_size_bytes=10, status=ResumeStatus.READY)
        s.add(res)
        await s.flush()
        ids = [str(uuid.uuid4()) for _ in chunks]
        s.add_all(ResumeChunk(id=cid, resume_id=res.id, section=ChunkSection.EXPERIENCE, chunk_index=i, text=body)
                  for i, (cid, body) in enumerate(zip(ids, chunks)))
        await s.flush()
        await replace_resume_rows(s, res.id, emp.id, list(zip(ids, chunks)))
        await s.commit()
        return emp.id, res.id


# --------------------------------------------------------------------------- migrations
async def test_models_and_migrations_match(database):
    """Autogenerate finds nothing to do: every model change has its migration (and nothing extra)."""
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    from app.db.base import Base
    from app.db.unmanaged import include_object

    def diff(sync_conn):
        ctx = MigrationContext.configure(sync_conn, opts={"compare_type": True, "include_object": include_object})
        return compare_metadata(ctx, Base.metadata)
    async with database.connect() as conn:
        assert await conn.run_sync(diff) == []


async def test_at_head(database):
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    async with database.connect() as conn:
        current = await conn.run_sync(lambda c: MigrationContext.configure(c).get_current_revision())
    assert current == ScriptDirectory.from_config(alembic_config()).get_current_head()


async def test_pre_migration_sqlite_database_is_upgraded(tmp_path):
    """A database made by Steps 3-14 (create_all, no alembic_version, without the 13b columns) is brought up to
    date and stamped, keeping its rows."""
    import sqlite3

    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db import session as session_module
    from app.db.session import BASELINE_REVISION

    from alembic import command

    path = tmp_path / "old.db"
    old = create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}")

    def make_old(sync_conn):
        # The Steps 3-14 schema (= revision 0001) without any record of migrations, and without a column
        # that Step 13b added later with ALTER TABLE: what an older install of the app has on disk.
        config = alembic_config()
        config.attributes["connection"] = sync_conn
        command.upgrade(config, BASELINE_REVISION)
        sync_conn.execute(text("DROP TABLE alembic_version"))
        sync_conn.execute(text("ALTER TABLE resume_skills DROP COLUMN years_basis"))
        sync_conn.execute(text("INSERT INTO skills (name) VALUES ('Python')"))
    async with old.begin() as conn:
        await conn.run_sync(make_old)
    await session_module.migrate(old)
    await old.dispose()
    db = sqlite3.connect(path)
    assert db.execute("SELECT name FROM skills").fetchall() == [("Python",)]
    assert "years_basis" in {r[1] for r in db.execute("PRAGMA table_info(resume_skills)")}
    from alembic.script import ScriptDirectory
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    assert db.execute("SELECT version_num FROM alembic_version").fetchall() == [(head,)]


@pytest.mark.skipif(IS_POSTGRES, reason="SQLite only: PostgreSQL alters tables in place")
async def test_sqlite_table_rebuild_keeps_child_rows():
    """Some migrations make SQLite rebuild a table (copy, DROP, rename). With foreign keys ON, dropping
    `resumes` would cascade-delete every chunk, skill and match result. migrate() switches them off for the
    migration: going down to 0001 (drops columns: a rebuild) and back up must keep every row."""
    from app.db.session import engine, migrate

    _, rid = await _resume(f"EMP-R{uuid.uuid4().hex[:6]}", ["kept chunk one", "kept chunk two"])
    async def chunks() -> int:
        async with SessionLocal() as s:
            return len((await s.scalars(select(ResumeChunk).where(ResumeChunk.resume_id == rid))).all())
    assert await chunks() == 2
    await migrate(engine, BASELINE, downgrade=True)
    await migrate(engine)
    assert await chunks() == 2
    async with engine.connect() as conn:                       # and foreign keys are enforced again
        assert (await conn.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1


# --------------------------------------------------------------------------- portability guards
async def test_long_text_is_cut_to_the_column(caplog):
    async with SessionLocal() as s:
        emp = Employee(employee_code="EMP-LONG", full_name="x" * 500, department="d" * 300)
        s.add(emp)
        await s.commit()
        await s.refresh(emp)
    assert (len(emp.full_name), len(emp.department)) == (200, 100)
    assert "employees.full_name: 500 characters cut" in caplog.text


async def test_times_are_utc_whatever_the_server_zone():
    from datetime import datetime, timezone

    async with SessionLocal() as s:
        if IS_POSTGRES:
            assert (await s.execute(text("SHOW timezone"))).scalar_one() == "UTC"
        emp = Employee(employee_code=f"EMP-T{uuid.uuid4().hex[:6]}", full_name="T")
        s.add(emp)
        await s.commit()
        await s.refresh(emp)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((emp.created_at - now).total_seconds()) < 120


async def test_jobs_without_dates_sort_last():
    from datetime import date

    from sqlalchemy.orm import selectinload

    _, rid = await _resume(f"EMP-O{uuid.uuid4().hex[:6]}", ["x"])
    async with SessionLocal() as s:
        s.add_all([Experience(resume_id=rid, company="NoDate", start_date=None),
                   Experience(resume_id=rid, company="Old", start_date=date(2015, 1, 1)),
                   Experience(resume_id=rid, company="New", start_date=date(2022, 1, 1))])
        await s.commit()
        res = await s.scalar(select(Resume).where(Resume.id == rid).options(selectinload(Resume.experiences)))
        assert [e.company for e in res.experiences] == ["New", "Old", "NoDate"]


# --------------------------------------------------------------------------- keyword search
async def test_keyword_search_finds_the_same_chunks():
    await ensure_keyword_index()
    e1, r1 = await _resume("EMP-K1", ["Built REST APIs with Node.js and Express for a retail client.",
                                      "Kubernetes clusters on AWS, Terraform, CI/CD with GitHub Actions."])
    e2, r2 = await _resume("EMP-K2", ["Machine learning models in Python; some Go services.",
                                      "Kubernetes basics."])
    async with SessionLocal() as s:
        hits = await keyword_search(s, ["Kubernetes", "Terraform"], [r1, r2])
        assert [h.resume_id for h in hits][0] == r1                       # two terms beat one
        assert {h.resume_id for h in hits} == {r1, r2}
        assert "[kubernetes]" in hits[0].snippet.lower() or "[Kubernetes]" in hits[0].snippet
        assert all(h.bm25 < 0 for h in hits)                             # more negative = better, both DBs
        assert [h.resume_id for h in await keyword_search(s, ["Node.js"], [r1, r2])] == [r1]
        assert [h.resume_id for h in await keyword_search(s, ["machine learning"], [r1, r2])] == [r2]
        assert await keyword_search(s, ["Kubernetes"], [r2]) and not await keyword_search(s, ["Cobol"], [r1, r2])
        assert await keyword_search(s, ["  ", '"'], [r1]) == []


# --------------------------------------------------------------------------- vector store
async def test_vector_store_round_trip(tmp_path):
    from app.db.session import engine
    from app.rag.vector_store import ChromaVectorStore, PgVectorStore, get_vector_store, store_kind

    assert get_vector_store().name == store_kind() == ("pgvector" if IS_POSTGRES else "chroma")
    # its own collection: the app's shared one holds the other tests' (differently sized) vectors
    store = PgVectorStore("roundtrip_8", engine) if IS_POSTGRES else ChromaVectorStore(str(tmp_path), "roundtrip_8")
    e1, r1 = await _resume("EMP-V1", ["a"])
    e2, r2 = await _resume("EMP-V2", ["b"])

    def unit(i: int, dim: int = 8) -> list[float]:
        return [1.0 if j == i else 0.0 for j in range(dim)]
    meta = lambda e, r: {"resume_id": r, "employee_id": e, "section": "experience", "chunk_index": 0}  # noqa: E731
    before = await store.count()
    await store.replace_resume(r1, ["v1a", "v1b"], [unit(0), unit(1)], ["k8s", "python"], [meta(e1, r1)] * 2)
    await store.replace_resume(r2, ["v2a"], [unit(2)], ["java"], [meta(e2, r2)])
    assert await store.count() == before + 3
    hits = await store.query(unit(1), 2)
    assert hits[0].chunk_id == "v1b" and hits[0].similarity == pytest.approx(1.0) and hits[0].employee_id == e1
    only = await store.query(unit(1), 5, employee_ids=[e2])
    assert [h.chunk_id for h in only] == ["v2a"] and only[0].similarity == pytest.approx(0.0)
    await store.replace_resume(r1, ["v1c"], [unit(3)], ["go"], [meta(e1, r1)])     # replace = old ones gone
    assert {h.chunk_id for h in await store.query(unit(3), 10, [e1])} == {"v1c"}
    await store.delete_resume(r2)
    assert await store.query(unit(2), 10, [e2]) == []


@pytest.mark.skipif(not IS_POSTGRES, reason="pgvector only")
async def test_pgvector_details():
    from app.db.session import engine
    from app.rag.vector_store import PgVectorStore, table_for

    store = PgVectorStore("test_collection_768", engine)
    e, r = await _resume("EMP-P1", ["x"])
    await store.replace_resume(r, ["p1"], [[0.1] * 768], ["x"], [{"resume_id": r, "employee_id": e, "section": "skills"}])
    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT table_name, dimensions, column_type FROM vector_collections "
                                       "WHERE name = 'test_collection_768'"))).one()
        assert tuple(row) == (table_for("test_collection_768"), 768, "vector")
        indexes = {i for (i,) in await conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = :t"),
                                                    {"t": row.table_name})}
        assert f"{row.table_name}_embedding" in indexes                # HNSW
    with pytest.raises(RuntimeError, match="768-dimension"):
        await PgVectorStore("test_collection_768", engine).replace_resume(
            r, ["p2"], [[0.1] * 1024], ["x"], [{"resume_id": r, "employee_id": e, "section": "skills"}])
    async with SessionLocal() as s:                                     # deleting the resume removes its vectors
        await s.delete(await s.get(Resume, r))
        await s.commit()
    assert await store.count() == 0
    # vectors bigger than an HNSW index allows: stored and searched exactly
    big = PgVectorStore("test_collection_3072", engine)
    e, r = await _resume("EMP-P2", ["x"])
    await big.replace_resume(r, ["b1"], [[0.01] * 3072], ["x"], [{"resume_id": r, "employee_id": e, "section": "skills"}])
    assert (await big.query([0.01] * 3072, 1))[0].chunk_id == "b1"
