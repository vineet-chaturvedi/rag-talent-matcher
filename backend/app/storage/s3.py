"""
STORAGE_BACKEND=s3: Amazon S3 (or any S3-compatible store via S3_ENDPOINT_URL: MinIO, Cloudflare R2, Ceph).

  S3_BUCKET           the bucket (create it with "Block all public access" on, versioning recommended)
  STORAGE_PREFIX      folder inside the bucket, default "resumes/"
  S3_KMS_KEY_ID       optional: encrypt with your own KMS key (SSE-KMS); otherwise S3-managed keys (SSE-S3)
  S3_REGION           default: AWS_REGION

Credentials: boto3's standard chain (ECS task role / EC2 instance profile on AWS, AWS_PROFILE on a laptop).
IAM permissions needed on arn:aws:s3:::<bucket>/<prefix>*: s3:PutObject, s3:GetObject, s3:DeleteObject
(+ kms:Encrypt/Decrypt/GenerateDataKey on the key when S3_KMS_KEY_ID is set).
boto3 is synchronous: calls run in worker threads.
"""
import asyncio

from app.storage.base import DownloadingStorage, FileMissingError, StorageError, join_prefix


def _sdk():
    try:
        import boto3
        import botocore
    except ImportError as exc:
        raise StorageError("STORAGE_BACKEND=s3 needs boto3: pip install -r requirements-cloud.txt") from exc
    return boto3, botocore


class S3Storage(DownloadingStorage):
    name = "s3"

    def __init__(self, bucket: str | None, prefix: str, region: str | None, endpoint_url: str | None,
                 kms_key_id: str | None, profile: str | None = None, client=None):
        if not bucket:
            raise StorageError("S3_BUCKET is not set in backend/.env")
        boto3, botocore = _sdk()
        self.bucket, self.prefix, self._kms = bucket, prefix, kms_key_id
        self._client = client or boto3.Session(profile_name=profile or None, region_name=region or None).client(
            "s3", endpoint_url=endpoint_url or None,
            config=botocore.config.Config(retries={"mode": "standard", "max_attempts": 5}, connect_timeout=10,
                                          read_timeout=60, max_pool_connections=32))
        self._errors = botocore.exceptions

    def describe(self) -> str:
        return f"s3://{self.bucket}/{self.prefix.strip('/')}/" if self.prefix.strip("/") else f"s3://{self.bucket}/"

    def _error(self, exc: Exception, key: str) -> StorageError:
        if isinstance(exc, self._errors.ClientError):
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                return FileMissingError(f"No file {key!r} in {self.describe()}")
            return StorageError(f"S3 {code}: {exc.response.get('Error', {}).get('Message', exc)}")
        return StorageError(f"S3: {type(exc).__name__}: {exc}")

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        extra = {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self._kms} if self._kms else \
                {"ServerSideEncryption": "AES256"}
        try:
            await asyncio.to_thread(self._client.put_object, Bucket=self.bucket, Key=join_prefix(self.prefix, key),
                                    Body=data, ContentType=content_type, **extra)
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def get(self, key: str) -> bytes:
        def read() -> bytes:
            body = self._client.get_object(Bucket=self.bucket, Key=join_prefix(self.prefix, key))["Body"]
            try:
                return body.read()
            finally:
                body.close()
        try:
            return await asyncio.to_thread(read)
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def delete(self, key: str) -> None:
        try:   # S3 answers 204 for a missing key too
            await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=join_prefix(self.prefix, key))
        except Exception as exc:
            raise self._error(exc, key) from exc

    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self.bucket, Key=join_prefix(self.prefix, key))
            return True
        except Exception as exc:
            if isinstance(self._error(exc, key), FileMissingError):
                return False
            raise self._error(exc, key) from exc

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
