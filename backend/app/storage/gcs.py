"""
STORAGE_BACKEND=gcs: Google Cloud Storage.

  GCS_BUCKET          the bucket (uniform bucket-level access + "public access prevention" enforced)
  STORAGE_PREFIX      folder inside the bucket, default "resumes/"
  GCS_KMS_KEY_NAME    optional: encrypt with your own Cloud KMS key (CMEK); otherwise Google-managed keys

Credentials: Application Default Credentials (the service account of Cloud Run / GKE / Compute Engine).
The service account needs roles/storage.objectUser on the bucket (or objectCreator + objectViewer + delete).
The google-cloud-storage client is synchronous: calls run in worker threads.
"""
import asyncio

from app.storage.base import DownloadingStorage, FileMissingError, StorageError, join_prefix


def _sdk():
    try:
        from google.api_core import exceptions
        from google.cloud import storage
    except ImportError as exc:
        raise StorageError("STORAGE_BACKEND=gcs needs google-cloud-storage: "
                           "pip install -r requirements-cloud.txt") from exc
    return storage, exceptions


class GCSStorage(DownloadingStorage):
    name = "gcs"

    def __init__(self, bucket: str | None, prefix: str, kms_key_name: str | None = None,
                 project: str | None = None, client=None):
        if not bucket:
            raise StorageError("GCS_BUCKET is not set in backend/.env")
        storage, self._errors = _sdk()
        self._client = client or storage.Client(project=project or None)
        self._bucket = self._client.bucket(bucket)
        self.bucket_name, self.prefix, self._kms = bucket, prefix, kms_key_name

    def describe(self) -> str:
        return f"gs://{self.bucket_name}/{self.prefix.strip('/')}/" if self.prefix.strip("/") else \
            f"gs://{self.bucket_name}/"

    def _blob(self, key: str):
        return self._bucket.blob(join_prefix(self.prefix, key), kms_key_name=self._kms or None)

    def _error(self, exc: Exception, key: str) -> StorageError:
        if isinstance(exc, self._errors.NotFound):
            return FileMissingError(f"No file {key!r} in {self.describe()}")
        return StorageError(f"Cloud Storage: {type(exc).__name__}: {exc}")

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        try:   # one request; the upload is atomic (the object appears complete or not at all)
            await asyncio.to_thread(self._blob(key).upload_from_string, data, content_type=content_type)
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def get(self, key: str) -> bytes:
        try:
            return await asyncio.to_thread(self._blob(key).download_as_bytes)
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self._blob(key).delete)
        except Exception as exc:
            if not isinstance(exc, self._errors.NotFound):
                raise self._error(exc, key) from exc

    async def exists(self, key: str) -> bool:
        try:
            return await asyncio.to_thread(self._blob(key).exists)
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
