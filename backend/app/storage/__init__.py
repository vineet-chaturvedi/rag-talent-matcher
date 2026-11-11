"""
Where uploaded resume files live (doc 21). One interface, four backends, chosen with STORAGE_BACKEND in .env:

  local   a folder on this machine (UPLOAD_DIR)                         development, one server
  s3      Amazon S3 (or an S3-compatible store: MinIO, Cloudflare R2)   AWS
  gcs     Google Cloud Storage                                          Google Cloud
  azure   Azure Blob Storage                                            Azure

Every file is addressed by a KEY: "<EMPLOYEE_CODE>/<first 16 characters of its SHA-256>.<ext>", the same on
every backend (the database's resumes.stored_path). The user's own file name is never used in storage.

Resumes are personal data. The cloud backends keep buckets/containers private (nothing is ever made public or
given a public link: the API streams files to signed-in admins only) and encrypted at rest, with your own KMS
key when one is configured. Credentials come from the platform (IAM role, service account, managed identity),
not from .env, wherever possible.
"""
from functools import lru_cache

from app.storage.base import FileMissingError, FileStorage, StorageError

__all__ = ["FileMissingError", "FileStorage", "StorageError", "get_storage", "make_storage"]


def make_storage(settings) -> FileStorage:
    kind = settings.storage_backend
    if kind == "local":
        from app.storage.local import LocalStorage
        return LocalStorage(settings.upload_dir)
    if kind == "s3":
        from app.storage.s3 import S3Storage
        return S3Storage(settings.s3_bucket, settings.storage_prefix, settings.s3_region or settings.aws_region,
                         settings.s3_endpoint_url, settings.s3_kms_key_id, settings.aws_profile)
    if kind == "gcs":
        from app.storage.gcs import GCSStorage
        return GCSStorage(settings.gcs_bucket, settings.storage_prefix, settings.gcs_kms_key_name)
    if kind == "azure":
        from app.storage.azure_blob import AzureBlobStorage
        return AzureBlobStorage(settings.azure_storage_container, settings.storage_prefix,
                                settings.azure_storage_account_url, settings.azure_storage_connection_string)
    raise StorageError(f"Unknown STORAGE_BACKEND {kind!r}: use local, s3, gcs or azure")


@lru_cache
def get_storage() -> FileStorage:
    """One shared instance per process (clients keep their connection pools)."""
    from app.config import get_settings
    return make_storage(get_settings())
