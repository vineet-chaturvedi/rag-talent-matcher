# Tests

```powershell
cd backend
pip install -r requirements.txt -r requirements-cloud.txt -r requirements-dev.txt
python -m pytest                      # SQLite + ChromaDB, in a temporary folder (about 20 s)
```

The same tests on PostgreSQL + pgvector (run them before deploying to a PostgreSQL database):

```powershell
docker compose up -d postgres         # from the repo root, or any PostgreSQL 16 with pgvector
$env:TEST_DATABASE_URL = "postgresql+asyncpg://rag:<password>@localhost:5432/rag_test"
python -m pytest
```

> The test database is **emptied** at the start (its tables are dropped). Use a database made for tests
> (`CREATE DATABASE rag_test`), never the real one.

What they cover, with the real SDKs and only the network faked:

| File | What |
|---|---|
| `test_provider_bedrock.py` | Amazon Bedrock: tools, streaming, the 3 structured-output modes, refused parameters, throttling, Titan / Cohere embeddings (boto3 against `fakes/cloud_models.py`) |
| `test_provider_vertex.py` | Vertex AI: Gemini (OpenAI-compatible endpoint), Claude on Vertex, embeddings, Google OAuth tokens from a service-account key |
| `test_database.py` | Migrations match the models (no drift), upgrading a pre-migration database, keyword search, vector store, long text, UTC times, NULL ordering |
| `test_storage.py` | The storage contract on local / S3 (moto) / Google Cloud Storage / Azure Blob (HTTP stand-ins), encryption headers, safe keys, old paths |
| `test_resume_files.py` | Upload → storage key, delete, the duplicate race, moving files to S3 (`scripts.migrate_files`) |
| `test_jobs.py` | Upload → READY and a judged match run through the worker; claims under contention; dead-worker recovery; graceful shutdown; the queue contract on SQS / Pub/Sub / Service Bus |

The tests never read `backend/.env`: every setting they need is set in `conftest.py`.
