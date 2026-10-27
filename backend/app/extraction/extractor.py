"""
One LLM call: resume text in -> validated, post-processed Profile out.
"""
import logging
import time
from dataclasses import dataclass

from pydantic import ValidationError

from app.extraction.postprocess import Profile, build_profile
from app.extraction.prompts import build_messages
from app.extraction.schema import ResumeExtraction
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

NS = 1_000_000_000
# The JSON schema is computed once; Ollama uses it to constrain every generated token.
EXTRACTION_SCHEMA = ResumeExtraction.model_json_schema()


class ExtractionOutputError(Exception):
    """The model's answer was unusable (cut off, or not valid for our schema). Worth retrying."""


@dataclass
class ExtractionOutcome:
    model: str
    llm_output: ResumeExtraction     # exactly what the model said (kept for auditing)
    profile: Profile                 # after verification + normalisation + date maths
    stats: dict                      # tokens and timings


async def extract_profile(
    ollama: OllamaClient,
    resume_text: str,
    model: str,
    num_ctx: int,
    max_output_tokens: int,
    max_input_chars: int,
) -> ExtractionOutcome:
    text = resume_text
    truncated = len(text) > max_input_chars
    if truncated:
        text = text[:max_input_chars]   # protect the context window; the warning is stored with the profile

    started = time.perf_counter()
    data = await ollama.chat(
        build_messages(text),
        model=model,
        temperature=0.0,                 # same input -> same output: extraction must be repeatable
        num_ctx=num_ctx,
        json_schema=EXTRACTION_SCHEMA,
        num_predict=max_output_tokens,
    )
    seconds = time.perf_counter() - started

    if data.get("done_reason") == "length":
        raise ExtractionOutputError(
            f"The model's answer was cut off after {max_output_tokens} tokens (EXTRACTION_MAX_OUTPUT_TOKENS)."
        )
    try:
        llm_output = ResumeExtraction.model_validate_json(data["message"]["content"])
    except ValidationError as exc:
        raise ExtractionOutputError(f"The model returned JSON that does not fit the schema: {exc}") from exc

    profile = build_profile(llm_output, resume_text)
    if truncated:
        profile.warnings.append(f"Resume text was longer than {max_input_chars} characters and was truncated.")

    stats = {
        "seconds": round(seconds, 1),
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "output_tokens_per_second": round(data["eval_count"] / (data["eval_duration"] / NS), 1)
        if data.get("eval_duration") else None,
    }
    logger.info("Extracted with %s in %.1fs: %d skills, %d jobs, %d rejected",
                model, seconds, len(profile.skills), len(profile.jobs), len(profile.rejected_skills))
    return ExtractionOutcome(model=model, llm_output=llm_output, profile=profile, stats=stats)
