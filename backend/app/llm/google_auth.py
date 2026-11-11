"""
Google Cloud credentials for Vertex AI: Application Default Credentials (ADC), nothing secret in .env.

Where ADC comes from, in Google's standard order:
  GOOGLE_APPLICATION_CREDENTIALS     a service-account key file (avoid in production: keys leak)
  `gcloud auth application-default login`     a developer's own login on a laptop
  the attached service account       Cloud Run, GKE (Workload Identity), Compute Engine: the recommended way
  workload identity federation       AWS, Azure or GitHub Actions identities exchanged for Google tokens

Access tokens live about an hour. GoogleToken refreshes them shortly before they expire, in a thread (the
refresh is a blocking HTTP call), and only once at a time.
"""
import asyncio
import logging

from app.llm.errors import LLMError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _sdk():
    try:
        import google.auth
        import google.auth.transport.requests
    except ImportError as exc:
        raise LLMError("vertex/ models need google-auth: pip install -r requirements-cloud.txt") from exc
    return google.auth


def default_credentials():
    """(credentials, project from ADC or None). Raises LLMError when no credentials can be found."""
    google_auth = _sdk()
    try:
        return google_auth.default(scopes=SCOPES)
    except google_auth.exceptions.DefaultCredentialsError as exc:
        raise LLMError(f"Vertex AI: no Google credentials found ({exc}). Run on Google Cloud with a service "
                       "account, or `gcloud auth application-default login`.") from exc


class GoogleToken:
    """An always-fresh OAuth access token for Google APIs."""

    def __init__(self, credentials):
        self.credentials = credentials
        self._lock = asyncio.Lock()

    async def get(self) -> str:
        # .valid = a token exists and is not within google-auth's refresh margin (a few minutes) of expiring
        if self.credentials.valid:
            return self.credentials.token
        async with self._lock:
            if not self.credentials.valid:
                google_auth = _sdk()
                try:
                    await asyncio.to_thread(self.credentials.refresh, google_auth.transport.requests.Request())
                except Exception as exc:
                    raise LLMError(f"Vertex AI: could not get a Google access token: {exc}") from exc
                logger.debug("Google access token refreshed")
        return self.credentials.token
