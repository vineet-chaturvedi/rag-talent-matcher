"""
File storage (app/storage): the same contract on all four backends, with the real SDKs:
local folder, S3 (moto's in-process AWS emulator), Google Cloud Storage and Azure Blob (HTTP stand-ins).
"""
import threading

import pytest

from app.storage import FileMissingError, StorageError, make_storage
from app.storage.base import check_key
from app.storage.local import LocalStorage
from tests.conftest import free_port, make_settings

PDF = b"%PDF-1.7 a small resume"


@pytest.fixture(scope="module")
def storage_url():
    import uvicorn

    from tests.fakes.cloud_models import wait_until_up
    from tests.fakes.cloud_storage import make_app

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(make_app(), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    wait_until_up(port)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


@pytest.fixture
def aws(monkeypatch):
    from moto import mock_aws

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    with mock_aws():
        import boto3
        boto3.client("s3", region_name="ap-south-1").create_bucket(
            Bucket="talent-resumes", CreateBucketConfiguration={"LocationConstraint": "ap-south-1"})
        yield


@pytest.fixture(params=["local", "s3", "gcs", "azure"])
async def storage(request, tmp_path, monkeypatch, storage_url):
    kind = request.param
    if kind == "local":
        s = make_storage(make_settings(storage_backend="local", upload_dir=str(tmp_path / "uploads")))
    elif kind == "s3":
        request.getfixturevalue("aws")
        s = make_storage(make_settings(storage_backend="s3", s3_bucket="talent-resumes", aws_region="ap-south-1"))
    elif kind == "gcs":
        monkeypatch.setenv("STORAGE_EMULATOR_HOST", storage_url)
        s = make_storage(make_settings(storage_backend="gcs", gcs_bucket="talent-resumes"))
    else:
        conn = ("DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
                "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
                f"BlobEndpoint={storage_url}/devstoreaccount1;")
        s = make_storage(make_settings(storage_backend="azure", azure_storage_container="resumes",
                                       azure_storage_connection_string=conn))
    yield s
    await s.close()


async def test_contract(storage):
    key = "EMP-1001/ab12cd34ef56ab78.pdf"
    assert not await storage.exists(key)
    await storage.put(key, PDF, "application/pdf")
    assert await storage.exists(key)
    assert await storage.get(key) == PDF
    await storage.put(key, PDF + b"!", "application/pdf")                 # replace
    assert await storage.get(key) == PDF + b"!"
    async with storage.local_path(key) as path:                             # what text extraction reads
        assert path.read_bytes() == PDF + b"!" and path.suffix == ".pdf"
    if storage.name != "local":
        assert not path.exists()                                            # the temporary copy is gone
    await storage.delete(key)
    await storage.delete(key)                                               # already gone: no error
    assert not await storage.exists(key)
    with pytest.raises(FileMissingError):
        await storage.get(key)
    with pytest.raises(StorageError):
        await storage.put("../escape.pdf", PDF, "application/pdf")
    assert storage.describe()


async def test_s3_encryption_and_prefix(aws):
    import boto3

    s3 = boto3.client("s3", region_name="ap-south-1")
    plain = make_storage(make_settings(storage_backend="s3", s3_bucket="talent-resumes", aws_region="ap-south-1"))
    await plain.put("EMP-1/a.pdf", PDF, "application/pdf")
    head = s3.head_object(Bucket="talent-resumes", Key="resumes/EMP-1/a.pdf")
    assert (head["ServerSideEncryption"], head["ContentType"]) == ("AES256", "application/pdf")
    key_id = boto3.client("kms", region_name="ap-south-1").create_key()["KeyMetadata"]["KeyId"]
    kms = make_storage(make_settings(storage_backend="s3", s3_bucket="talent-resumes", aws_region="ap-south-1",
                                     s3_kms_key_id=key_id, storage_prefix=""))
    await kms.put("EMP-1/b.pdf", PDF, "application/pdf")
    head = s3.head_object(Bucket="talent-resumes", Key="EMP-1/b.pdf")
    assert head["ServerSideEncryption"] == "aws:kms" and key_id in head["SSEKMSKeyId"]
    assert await kms.get("EMP-1/b.pdf") == PDF
    await plain.close(); await kms.close()


async def test_misconfiguration_is_explained():
    with pytest.raises(StorageError, match="S3_BUCKET"):
        make_storage(make_settings(storage_backend="s3"))
    with pytest.raises(StorageError, match="GCS_BUCKET"):
        make_storage(make_settings(storage_backend="gcs"))
    with pytest.raises(StorageError, match="AZURE_STORAGE"):
        make_storage(make_settings(storage_backend="azure", azure_storage_container="c"))


def test_keys_are_safe():
    assert check_key("EMP-1001/ab12.pdf") == "EMP-1001/ab12.pdf"
    for bad in ["", "/abs.pdf", "../x.pdf", "a/../../x", "a//b.pdf", "a/b c.pdf", "a\\b.pdf"]:
        with pytest.raises(StorageError):
            check_key(bad)


async def test_local_reads_paths_stored_before_step_15(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                                   # stored paths were relative to backend/
    (tmp_path / "data/uploads/EMP-1").mkdir(parents=True)
    (tmp_path / "data/uploads/EMP-1/old.pdf").write_bytes(PDF)
    (tmp_path / "secret.txt").write_text("no")
    store = LocalStorage("./data/uploads")
    assert await store.get("data/uploads/EMP-1/old.pdf") == PDF                 # legacy relative path
    assert await store.get(str(tmp_path / "data/uploads/EMP-1/old.pdf")) == PDF  # legacy absolute path
    assert await store.get("EMP-1/old.pdf") == PDF                              # a key
    for outside in ["secret.txt", str(tmp_path / "secret.txt"), "data/uploads/../../secret.txt"]:
        with pytest.raises(StorageError):
            await store.get(outside)
