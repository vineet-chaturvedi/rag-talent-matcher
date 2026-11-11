"""
Move resume files into the storage backend set in backend/.env (STORAGE_BACKEND), or check them (doc 21).

    python -m scripts.migrate_files --check                  is every resume's file where the database says?
    python -m scripts.migrate_files --from-local ./data/uploads
                                                             copy local files into the configured backend
                                                             (s3 / gcs / azure, or local: just tidy the paths)

For every resume: read the file from the local folder (the path stored before Step 15, or a storage key),
check it against the SHA-256 fingerprint saved at upload, store it under its key in the target, check that it
arrived, and only then point the database row at the key. Safe to run again: files already in place are
skipped. Local files are never deleted (remove the folder yourself once you've checked the result).
"""
import argparse
import asyncio
import hashlib
import logging
import sys

from sqlalchemy import select

logger = logging.getLogger("migrate_files")


def _key_for(resume) -> str:
    """The key an upload of this file gets today (app/ingestion/storage.py: storage_key)."""
    from app.ingestion.storage import ALLOWED_TYPES, safe_folder_name

    ext = next(e for e, (mime, _) in ALLOWED_TYPES.items() if mime == resume.mime_type)
    return f"{safe_folder_name(resume.employee.employee_code)}/{resume.file_hash[:16]}{ext}"


async def check() -> int:
    from sqlalchemy.orm import selectinload

    from app.db.models import Resume
    from app.db.session import SessionLocal
    from app.storage import get_storage

    storage = get_storage()
    missing = 0
    async with SessionLocal() as s:
        resumes = (await s.scalars(select(Resume).options(selectinload(Resume.employee)))).all()
    for r in resumes:
        if not await storage.exists(r.stored_path):
            missing += 1
            logger.error("resume %s (%s, %s): missing at %s", r.id, r.employee.employee_code, r.original_filename,
                         r.stored_path)
    logger.info("%d resumes, %d files missing in %s", len(resumes), missing, storage.describe())
    return 1 if missing else 0


async def migrate(local_dir: str, dry_run: bool) -> int:
    from sqlalchemy.orm import selectinload

    from app.db.models import Resume
    from app.db.session import SessionLocal
    from app.storage import FileMissingError, StorageError, get_storage
    from app.storage.local import LocalStorage

    source, target = LocalStorage(local_dir), get_storage()
    moved = skipped = failed = 0
    logger.info("From %s to %s%s", source.describe(), target.describe(), " (dry run)" if dry_run else "")
    async with SessionLocal() as s:
        resumes = (await s.scalars(select(Resume).options(selectinload(Resume.employee)).order_by(Resume.id))).all()
        for r in resumes:
            key = _key_for(r)
            try:
                if r.stored_path == key and await target.exists(key):
                    skipped += 1
                    continue
                data = await source.get(r.stored_path)
                if hashlib.sha256(data).hexdigest() != r.file_hash:
                    raise StorageError("the file's content doesn't match its fingerprint (changed or corrupt)")
                if not dry_run:
                    await target.put(key, data, r.mime_type)
                    if hashlib.sha256(await target.get(key)).hexdigest() != r.file_hash:
                        raise StorageError("the stored copy differs from the original")
                    r.stored_path = key
                    await s.commit()                 # row by row: an interruption loses nothing
                moved += 1
            except (FileMissingError, StorageError) as exc:
                failed += 1
                logger.error("resume %s (%s): %s", r.id, r.stored_path, exc)
    logger.info("%d moved, %d already in place, %d failed%s", moved, skipped, failed,
                " (dry run: nothing written)" if dry_run else "")
    return 1 if failed else 0


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report resumes whose file is missing")
    group.add_argument("--from-local", metavar="DIR", help="copy files from this local upload folder")
    parser.add_argument("--dry-run", action="store_true", help="with --from-local: check only, write nothing")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from app.db.session import engine, init_db
    from app.storage import get_storage
    await init_db()
    try:
        return await check() if args.check else await migrate(args.from_local, args.dry_run)
    finally:
        await get_storage().close()
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
