"""
STORAGE_BACKEND=azure: Azure Blob Storage.

  AZURE_STORAGE_CONTAINER           the container (private access level; the account with "Allow Blob
                                    anonymous access" disabled)
  AZURE_STORAGE_ACCOUNT_URL         https://<account>.blob.core.windows.net   (recommended: managed identity)
  AZURE_STORAGE_CONNECTION_STRING   alternative for development / Azurite (contains a secret: keep out of git)
  STORAGE_PREFIX                    folder inside the container, default "resumes/"

Credentials with ACCOUNT_URL: DefaultAzureCredential (the managed identity of Container Apps / AKS / App
Service, `az login` on a laptop). It needs the "Storage Blob Data Contributor" role on the container.
Encryption at rest is always on (Microsoft-managed keys, or customer-managed keys set on the account).
Uses the SDK's async client (no threads needed).
"""
from app.storage.base import DownloadingStorage, FileMissingError, StorageError, join_prefix


def _sdk():
    try:
        from azure.core import exceptions
        from azure.storage.blob import ContentSettings
        from azure.storage.blob.aio import BlobServiceClient
    except ImportError as exc:
        raise StorageError("STORAGE_BACKEND=azure needs azure-storage-blob and azure-identity: "
                           "pip install -r requirements-cloud.txt") from exc
    return BlobServiceClient, ContentSettings, exceptions


class AzureBlobStorage(DownloadingStorage):
    name = "azure"

    def __init__(self, container: str | None, prefix: str, account_url: str | None,
                 connection_string: str | None, service=None):
        if not container:
            raise StorageError("AZURE_STORAGE_CONTAINER is not set in backend/.env")
        BlobServiceClient, self._content_settings, self._errors = _sdk()
        self._credential = None
        if service is None:
            if connection_string:
                service = BlobServiceClient.from_connection_string(connection_string)
            elif account_url:
                from azure.identity.aio import DefaultAzureCredential
                self._credential = DefaultAzureCredential()
                service = BlobServiceClient(account_url, credential=self._credential)
            else:
                raise StorageError("Set AZURE_STORAGE_ACCOUNT_URL (managed identity) or "
                                   "AZURE_STORAGE_CONNECTION_STRING in backend/.env")
        self._service = service
        self._container = service.get_container_client(container)
        self.container, self.prefix = container, prefix

    def describe(self) -> str:
        account = getattr(self._service, "account_name", "") or "azure"
        return f"azure://{account}/{self.container}/{self.prefix.strip('/')}/"

    def _error(self, exc: Exception, key: str) -> StorageError:
        if isinstance(exc, self._errors.ResourceNotFoundError):
            return FileMissingError(f"No file {key!r} in {self.describe()}")
        return StorageError(f"Azure Blob Storage: {type(exc).__name__}: {exc}")

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        try:   # a single-shot upload commits the whole blob at once
            await self._container.upload_blob(join_prefix(self.prefix, key), data, overwrite=True,
                                              content_settings=self._content_settings(content_type=content_type))
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def get(self, key: str) -> bytes:
        try:
            stream = await self._container.download_blob(join_prefix(self.prefix, key))
            return await stream.readall()
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def delete(self, key: str) -> None:
        try:
            await self._container.delete_blob(join_prefix(self.prefix, key), delete_snapshots="include")
        except Exception as exc:
            if not isinstance(exc, self._errors.ResourceNotFoundError):
                raise self._error(exc, key) from exc

    async def exists(self, key: str) -> bool:
        try:
            return await self._container.get_blob_client(join_prefix(self.prefix, key)).exists()
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def close(self) -> None:
        await self._service.close()
        if self._credential is not None:
            await self._credential.close()
