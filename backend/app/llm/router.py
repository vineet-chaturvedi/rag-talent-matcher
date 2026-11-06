"""
The model router: ONE object the whole app talks to (app.state.ollama), which sends every request to the
provider named in the model setting. The rest of the code never knows which provider answers.

A model setting is "<provider>/<model>". Without a known provider prefix it is an Ollama model, so all
existing settings (qwen2.5:7b, nomic-embed-text, hf.co/...) keep working unchanged.

  prefix       chat   embeddings   service                                   settings in backend/.env
  ollama/      yes    yes          local Ollama (the default)                OLLAMA_BASE_URL
  openai/      yes    yes          OpenAI (GPT, text-embedding-3-*)          OPENAI_API_KEY, OPENAI_BASE_URL
  azure/       yes    yes          Azure OpenAI (name = your deployment)     AZURE_OPENAI_API_KEY, _ENDPOINT, _API_VERSION
  anthropic/   yes    -            Anthropic (Claude)                        ANTHROPIC_API_KEY
  gemini/      yes    yes          Google Gemini                             GEMINI_API_KEY
  compat/      yes    yes          any OpenAI-compatible server              COMPAT_BASE_URL, COMPAT_API_KEY
  voyage/      -      yes          Voyage AI                                 VOYAGE_API_KEY
  cohere/      -      yes          Cohere                                    COHERE_API_KEY

Examples:  QUALITY_LLM_MODEL=anthropic/claude-sonnet-4-5   EMBED_MODEL=openai/text-embedding-3-large
           AGENT_MODEL_ROLE=gemini/gemini-2.5-flash          EMBED_MODEL=voyage/voyage-3.5

Data protection: resumes are personal data. A provider outside this PC/network is refused unless
ALLOW_CLOUD_MODELS=true (a deliberate decision, after checking contracts and the law: DPDP, GDPR).
Providers are created on first use, so a missing SDK or key only matters for the models actually chosen.
"""
import ipaddress
import logging
from typing import Any
from urllib.parse import urlparse

from app.llm.errors import LLMError
from app.llm.ollama_client import OllamaClient, normalize_model_name

logger = logging.getLogger(__name__)

CHAT_PROVIDERS = {"ollama", "openai", "azure", "anthropic", "gemini", "compat"}
EMBED_PROVIDERS = {"ollama", "openai", "azure", "gemini", "compat", "voyage", "cohere"}
PROVIDERS = CHAT_PROVIDERS | EMBED_PROVIDERS
LABEL = {"ollama": "Ollama", "openai": "OpenAI", "azure": "Azure OpenAI", "anthropic": "Anthropic",
         "gemini": "Google Gemini", "compat": "OpenAI-compatible server", "voyage": "Voyage AI", "cohere": "Cohere"}


def make_model_client(settings) -> "ModelRouter":
    """The client every part of the app (and every script) uses for models of any provider."""
    return ModelRouter(settings)


def split_model(spec: str) -> tuple[str, str]:
    """'anthropic/claude-x' -> ('anthropic', 'claude-x'); 'qwen2.5:7b' or 'hf.co/a/b' -> ('ollama', ...)."""
    head, sep, rest = (spec or "").partition("/")
    if sep and head.lower() in PROVIDERS and rest:
        return head.lower(), rest
    return "ollama", spec


def is_local_url(url: str | None) -> bool:
    """localhost, 127.x, or a private network address (a company server): data stays in the organisation."""
    host = urlparse(url or "").hostname or ""
    if host in ("localhost", "host.docker.internal") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


class ModelRouter:
    """Same methods as OllamaClient (chat, chat_stream, embed, version, list_models, close), any provider."""

    def __init__(self, settings, ollama: OllamaClient | None = None):
        self.settings = settings
        self.ollama = ollama or OllamaClient(settings.ollama_base_url, settings.ollama_timeout_seconds,
                                             settings.llm_think)
        self._chat: dict[str, Any] = {}
        self._embed: dict[str, Any] = {}

    # ------------------------------------------------------------------ which provider, allowed or not
    def is_cloud(self, provider: str) -> bool:
        if provider == "ollama":
            return not is_local_url(self.settings.ollama_base_url)
        if provider == "compat":
            return not is_local_url(self.settings.compat_base_url)
        return True

    def is_cloud_model(self, spec: str) -> bool:
        """Cloud provider, a remote Ollama, or an Ollama cloud model (name ending in -cloud runs at ollama.com)."""
        provider, name = split_model(spec)
        if provider == "ollama" and (name.endswith("-cloud") or name.endswith(":cloud")):
            return True
        return self.is_cloud(provider)

    def _check_allowed(self, provider: str, model: str) -> None:
        if self.is_cloud_model(model) and not self.settings.allow_cloud_models:
            raise LLMError(
                f"{model} runs at {LABEL[provider]}, outside this computer/network. Resumes are personal data, "
                "so cloud models are off until you set ALLOW_CLOUD_MODELS=true in backend/.env "
                "(after checking the provider's data-protection terms).")

    def configuration_problem(self, spec: str, kind: str = "chat") -> str | None:
        """Why this model can't be used as configured (None = fine). For the health check; never calls the API."""
        provider, _ = split_model(spec)
        if kind == "chat" and provider not in CHAT_PROVIDERS:
            return f"{LABEL[provider]} has no chat models (embeddings only)"
        if kind == "embed" and provider not in EMBED_PROVIDERS:
            return f"{LABEL[provider]} has no embedding models"
        if self.is_cloud_model(spec) and not self.settings.allow_cloud_models:
            return "cloud models are off (ALLOW_CLOUD_MODELS=false)"
        s = self.settings
        missing = {
            "openai": not s.openai_api_key and "OPENAI_API_KEY",
            "azure": not (s.azure_openai_api_key and s.azure_openai_endpoint) and "AZURE_OPENAI_API_KEY / _ENDPOINT",
            "anthropic": not s.anthropic_api_key and "ANTHROPIC_API_KEY",
            "gemini": not s.gemini_api_key and "GEMINI_API_KEY",
            "compat": not s.compat_base_url and "COMPAT_BASE_URL",
            "voyage": not s.voyage_api_key and "VOYAGE_API_KEY",
            "cohere": not s.cohere_api_key and "COHERE_API_KEY",
        }.get(provider)
        return f"{missing} is not set" if missing else None

    # ------------------------------------------------------------------ providers, created on first use
    def _chat_provider(self, provider: str):
        if provider not in self._chat:
            s, t = self.settings, self.settings.cloud_timeout_seconds
            from app.llm.openai_compat import OpenAICompatProvider
            if provider == "openai":
                self._chat[provider] = OpenAICompatProvider.openai(s.openai_api_key, s.openai_base_url, t)
            elif provider == "azure":
                self._chat[provider] = OpenAICompatProvider.azure(s.azure_openai_api_key, s.azure_openai_endpoint,
                                                                  s.azure_openai_api_version, t)
            elif provider == "gemini":
                self._chat[provider] = OpenAICompatProvider.gemini(s.gemini_api_key, s.gemini_openai_base_url, t)
            elif provider == "compat":
                self._chat[provider] = OpenAICompatProvider.compat(s.compat_api_key, s.compat_base_url, t)
            elif provider == "anthropic":
                from app.llm.anthropic_client import AnthropicProvider
                self._chat[provider] = AnthropicProvider(s.anthropic_api_key, s.anthropic_base_url, t,
                                                         s.anthropic_max_tokens)
            else:
                raise LLMError(f"{LABEL.get(provider, provider)} has no chat models (embeddings only)",
                               retryable=True)
        return self._chat[provider]

    def _embed_provider(self, provider: str):
        if provider not in self._embed:
            s, t = self.settings, self.settings.cloud_timeout_seconds
            from app.llm import embedding_apis as apis
            if provider == "voyage":
                self._embed[provider] = apis.VoyageEmbedder(s.voyage_api_key, t, s.voyage_base_url)
            elif provider == "cohere":
                self._embed[provider] = apis.CohereEmbedder(s.cohere_api_key, t, s.cohere_base_url)
            elif provider == "gemini":
                self._embed[provider] = apis.GeminiEmbedder(s.gemini_api_key, t, s.gemini_native_base_url)
            elif provider in ("openai", "azure", "compat"):
                self._embed[provider] = self._chat_provider(provider)   # same client does both
            else:
                raise LLMError(f"{LABEL.get(provider, provider)} has no embedding models", retryable=True)
        return self._embed[provider]

    # ------------------------------------------------------------------ the OllamaClient interface
    async def chat(self, messages, model: str, temperature: float = 0.0, num_ctx: int | None = None,
                   json_schema: dict | None = None, num_predict: int | None = None,
                   tools: list[dict] | None = None) -> dict[str, Any]:
        provider, name = split_model(model)
        self._check_allowed(provider, model)
        if provider == "ollama":
            return await self.ollama.chat(messages, name, temperature, num_ctx, json_schema, num_predict, tools)
        return await self._chat_provider(provider).chat(messages, name, temperature, num_ctx, json_schema,
                                                         num_predict, tools)

    async def chat_stream(self, messages, model: str, tools: list[dict] | None = None, temperature: float = 0.0,
                          num_ctx: int | None = None, num_predict: int | None = None):
        provider, name = split_model(model)
        self._check_allowed(provider, model)
        if provider == "ollama":
            source = self.ollama.chat_stream(messages, name, tools=tools, temperature=temperature,
                                             num_ctx=num_ctx, num_predict=num_predict)
        else:
            source = self._chat_provider(provider).chat_stream(messages, name, tools=tools, temperature=temperature,
                                                               num_ctx=num_ctx, num_predict=num_predict)
        async for chunk in source:
            yield chunk

    async def embed(self, texts: list[str], model: str, kind: str = "document") -> list[list[float]]:
        provider, name = split_model(model)
        self._check_allowed(provider, model)
        if provider == "ollama":
            return await self.ollama.embed(texts, name, kind)
        return await self._embed_provider(provider).embed(texts, name, kind, self.settings.embed_dimensions)

    async def version(self) -> str:
        return await self.ollama.version()

    async def list_models(self) -> list[str]:
        return await self.ollama.list_models()

    def uses_ollama(self) -> bool:
        return any(split_model(m)[0] == "ollama" for m in self.distinct_models().values())

    def distinct_models(self) -> dict[str, str]:
        s = self.settings
        return {"embed_model": s.embed_model, "fast_llm_model": s.fast_llm_model,
                "quality_llm_model": s.quality_llm_model, "extraction_model": s.extraction_model,
                "role_parse_model": s.role_parse_model, "judge_model": s.judge_model, "agent_model": s.agent_model}

    def model_health(self, spec: str, installed: set[str] | None, kind: str = "chat") -> dict[str, Any]:
        """{"name", "installed", "provider", "problem"} for the health check. installed: Ollama's model list."""
        provider, name = split_model(spec)
        if provider == "ollama":
            problem = self.configuration_problem(spec, kind)        # e.g. a -cloud model while cloud is off
            if problem is None and (installed is None or normalize_model_name(name) not in installed):
                problem = "Ollama is not reachable" if installed is None else f"not pulled (ollama pull {name})"
            return {"name": spec, "installed": problem is None, "provider": "Ollama", "problem": problem}
        problem = self.configuration_problem(spec, kind)
        return {"name": spec, "installed": problem is None, "provider": LABEL[provider], "problem": problem}

    def cloud_models_in_use(self) -> list[str]:
        return sorted({m for m in self.distinct_models().values() if self.is_cloud_model(m)})

    async def close(self) -> None:
        await self.ollama.close()
        for client in {id(c): c for c in [*self._chat.values(), *self._embed.values()]}.values():
            await client.close()
