"""
LLM call(s): resume text in -> validated, post-processed Profile out.

A resume that fits the model's context is read in ONE call. A longer one is split at section boundaries
into parts that each fit, the parts are read one after another, and their jobs/projects/education are
joined. Version 1 cut long resumes off at EXTRACTION_MAX_INPUT_CHARS, so everything after that was lost.
"""
import logging
import time
from dataclasses import dataclass

from pydantic import ValidationError

from app.extraction.postprocess import Profile, build_profile
from app.extraction.prompts import build_messages
from app.extraction.schema import ResumeExtraction
from app.extraction.sections import split_sections
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
    llm_output: ResumeExtraction     # exactly what the model said (joined, for long resumes)
    profile: Profile                 # after verification + normalisation + date maths
    stats: dict                      # tokens and timings


def split_for_model(text: str, max_chars: int) -> list[str]:
    """
    The resume in parts of at most max_chars, cut at section boundaries (a section longer than that is cut
    at entry or paragraph boundaries). One part when it fits. Parts keep the header (name and title) so
    each part has context.
    """
    if len(text) <= max_chars:
        return [text]
    lines, sections = split_sections(text)
    pieces: list[str] = []
    for s in sections:
        start = s.heading_line if s.heading_line is not None else s.start
        block = "\n".join(lines[start:s.end]).strip()
        while len(block) > max_chars:                     # a very long section: cut at a blank line or line
            cut = block.rfind("\n\n", 0, max_chars)
            cut = cut if cut > max_chars // 2 else block.rfind("\n", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            pieces.append(block[:cut].strip())
            block = block[cut:].strip()
        if block:
            pieces.append(block)
    header = pieces[0][:300] if sections and sections[0].kind == "header" else ""
    parts, current = [], ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > max_chars:
            parts.append(current)
            current = f"{header}\n\n{piece}" if header and not piece.startswith(header) else piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        parts.append(current)
    return parts


def _merge(answers: list[ResumeExtraction]) -> ResumeExtraction:
    """Join the answers for the parts of a long resume; the first headline/summary found wins."""
    if len(answers) == 1:
        return answers[0]

    def unique(items, key):
        seen, out = set(), []
        for item in items:
            k = key(item)
            if k not in seen:
                seen.add(k)
                out.append(item)
        return out

    def low(text):
        return (text or "").strip().lower()

    # An entry cut by a part boundary can be reported by both parts: keep it once.
    return ResumeExtraction(
        headline=next((a.headline for a in answers if a.headline), None),
        summary=next((a.summary for a in answers if a.summary), None),
        experience=unique((j for a in answers for j in a.experience), lambda j: (low(j.company), low(j.title), low(j.start))),
        projects=unique((p for a in answers for p in a.projects), lambda p: low(p.name)),
        education=unique((e for a in answers for e in a.education), lambda e: (low(e.degree), low(e.institution))),
        certifications=unique((c for a in answers for c in a.certifications), low),
    )


async def extract_profile(
    ollama: OllamaClient,
    resume_text: str,
    model: str,
    num_ctx: int,
    max_output_tokens: int,
    max_input_chars: int,
) -> ExtractionOutcome:
    parts = split_for_model(resume_text, max_input_chars)
    answers: list[ResumeExtraction] = []
    seconds = 0.0
    prompt_tokens = output_tokens = 0
    eval_ns = 0
    for number, part in enumerate(parts, start=1):
        started = time.perf_counter()
        data = await ollama.chat(
            build_messages(part, number, len(parts)),
            model=model,
            temperature=0.0,                 # same input -> same output: extraction must be repeatable
            num_ctx=num_ctx,
            json_schema=EXTRACTION_SCHEMA,
            num_predict=max_output_tokens,
        )
        seconds += time.perf_counter() - started
        if data.get("done_reason") == "length":
            raise ExtractionOutputError(
                f"The model's answer was cut off after {max_output_tokens} tokens (EXTRACTION_MAX_OUTPUT_TOKENS)."
            )
        try:
            answers.append(ResumeExtraction.model_validate_json(data["message"]["content"]))
        except ValidationError as exc:
            raise ExtractionOutputError(f"The model returned JSON that does not fit the schema: {exc}") from exc
        prompt_tokens += data.get("prompt_eval_count") or 0
        output_tokens += data.get("eval_count") or 0
        eval_ns += data.get("eval_duration") or 0

    llm_output = _merge(answers)
    profile = build_profile(llm_output, resume_text)
    if len(parts) > 1:
        profile.warnings.append(f"Long resume: read by the model in {len(parts)} parts.")

    stats = {
        "seconds": round(seconds, 1),
        "parts": len(parts),
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "output_tokens_per_second": round(output_tokens / (eval_ns / NS), 1) if eval_ns else None,
    }
    logger.info("Extracted with %s in %.1fs (%d part(s)): %d skills, %d jobs, %d projects, %d rejected",
                model, seconds, len(parts), len(profile.skills), len(profile.jobs), len(profile.projects),
                len(profile.rejected_skills))
    return ExtractionOutcome(model=model, llm_output=llm_output, profile=profile, stats=stats)
