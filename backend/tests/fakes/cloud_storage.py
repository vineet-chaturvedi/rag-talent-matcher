"""
Stand-ins for Google Cloud Storage (its JSON API, reached via STORAGE_EMULATOR_HOST) and Azure Blob Storage
(its REST API, reached via a connection string's BlobEndpoint), in memory, over real HTTP: the REAL
google-cloud-storage and azure-storage-blob SDKs are tested end to end. Only the network is faked.
"""
import base64
import hashlib
import json
import re
from email.utils import formatdate
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

GCS: dict[tuple[str, str], dict] = {}        # (bucket, name) -> {"data", "content_type", "kms"}
AZURE: dict[tuple[str, str], dict] = {}      # (container, name) -> {"data", "content_type"}


def make_app() -> FastAPI:
    app = FastAPI()

    # ------------------------------------------------------------------ Google Cloud Storage (JSON API)
    def gcs_resource(bucket: str, name: str) -> dict:
        obj = GCS[(bucket, name)]
        md5 = base64.b64encode(hashlib.md5(obj["data"]).digest()).decode()
        return {"kind": "storage#object", "id": f"{bucket}/{name}/1", "name": name, "bucket": bucket,
                "generation": "1", "metageneration": "1", "contentType": obj["content_type"],
                "size": str(len(obj["data"])), "md5Hash": md5, **({"kmsKeyName": obj["kms"]} if obj["kms"] else {})}

    def not_found() -> JSONResponse:
        return JSONResponse({"error": {"code": 404, "message": "No such object"}}, status_code=404)

    @app.post("/upload/storage/v1/b/{bucket}/o")
    async def gcs_upload(bucket: str, r: Request):
        assert r.query_params.get("uploadType") == "multipart", "expected a multipart upload"
        body = await r.body()
        boundary = re.search(r'boundary="?([^";]+)"?', r.headers["content-type"]).group(1).encode()
        parts = [p for p in body.split(b"--" + boundary) if p.strip() not in (b"", b"--")]
        meta = json.loads(parts[0].split(b"\r\n\r\n", 1)[1].strip())
        head, data = parts[1].split(b"\r\n\r\n", 1)
        content_type = re.search(rb"content-type:\s*([^\r\n]+)", head, re.I).group(1).decode()
        name = meta["name"]
        GCS[(bucket, name)] = {"data": data[:-2] if data.endswith(b"\r\n") else data, "content_type": content_type,
                               "kms": r.query_params.get("kmsKeyName")}
        return gcs_resource(bucket, name)

    @app.get("/download/storage/v1/b/{bucket}/o/{name:path}")
    async def gcs_download(bucket: str, name: str):
        name = unquote(name)
        if (bucket, name) not in GCS:
            return not_found()
        obj = GCS[(bucket, name)]
        md5 = base64.b64encode(hashlib.md5(obj["data"]).digest()).decode()
        return Response(obj["data"], media_type=obj["content_type"],
                        headers={"x-goog-hash": f"md5={md5}", "x-goog-generation": "1"})

    @app.get("/storage/v1/b/{bucket}/o/{name:path}")
    async def gcs_get(bucket: str, name: str):
        name = unquote(name)
        return gcs_resource(bucket, name) if (bucket, name) in GCS else not_found()

    @app.delete("/storage/v1/b/{bucket}/o/{name:path}")
    async def gcs_delete(bucket: str, name: str):
        name = unquote(name)
        if GCS.pop((bucket, name), None) is None:
            return not_found()
        return Response(status_code=204)

    # ------------------------------------------------------------------ Azure Blob Storage (REST)
    def azure_headers(extra: dict | None = None) -> dict:
        return {"ETag": '"0x8D9"', "Last-Modified": formatdate(usegmt=True), "x-ms-request-id": "r1",
                "x-ms-version": "2025-01-05", "Date": formatdate(usegmt=True), **(extra or {})}

    def azure_missing(head: bool = False) -> Response:
        body = b"" if head else b'<?xml version="1.0" encoding="utf-8"?><Error><Code>BlobNotFound</Code>' \
                                b"<Message>The specified blob does not exist.</Message></Error>"
        return Response(body, status_code=404, media_type="application/xml",
                        headers=azure_headers({"x-ms-error-code": "BlobNotFound"}))

    @app.api_route("/{account}/{container}/{name:path}", methods=["PUT", "GET", "HEAD", "DELETE"])
    async def azure_blob(account: str, container: str, name: str, r: Request):
        assert r.headers.get("authorization", "").startswith("SharedKey "), "requests must be signed"
        key = (container, unquote(name))
        if r.method == "PUT":
            assert r.headers.get("x-ms-blob-type") == "BlockBlob"
            AZURE[key] = {"data": await r.body(), "content_type": r.headers.get("x-ms-blob-content-type", "")}
            md5 = base64.b64encode(hashlib.md5(AZURE[key]["data"]).digest()).decode()
            return Response(status_code=201, headers=azure_headers({"Content-MD5": md5,
                                                                    "x-ms-request-server-encrypted": "true"}))
        if key not in AZURE:
            return azure_missing(head=r.method == "HEAD")
        blob = AZURE[key]
        if r.method == "DELETE":
            del AZURE[key]
            return Response(status_code=202, headers=azure_headers())
        props = {"Content-Type": blob["content_type"], "x-ms-blob-type": "BlockBlob",
                 "Content-Length": str(len(blob["data"])), "x-ms-server-encrypted": "true"}
        if r.method == "HEAD":
            return Response(status_code=200, headers=azure_headers(props))
        data, size = blob["data"], len(blob["data"])
        rng = r.headers.get("x-ms-range") or r.headers.get("range")
        if rng:
            start, end = (int(x) for x in rng.split("=")[1].split("-"))
            part = data[start:end + 1]
            return Response(part, status_code=206, headers=azure_headers({
                **props, "Content-Length": str(len(part)), "Content-Range": f"bytes {start}-{start + len(part) - 1}/{size}"}))
        return Response(data, status_code=200, headers=azure_headers(props))

    @app.get("/health")
    async def health():
        return Response("ok")

    return app
