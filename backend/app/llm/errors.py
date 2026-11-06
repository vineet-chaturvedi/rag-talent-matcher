"""
The one error type for every model provider (Ollama, OpenAI, Anthropic, Gemini ...).

Callers catch it in one place (`except OllamaError` / `except LLMError`: the same class). `retryable` tells the
background worker what to do:
  True  = not the resume's fault (service down, rate limit, missing key or model): pause and try again later.
  False = this request itself was refused (e.g. too long, blocked content): count it as a failed attempt,
          so one bad resume can't block the queue forever.
"""


class LLMError(Exception):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable
