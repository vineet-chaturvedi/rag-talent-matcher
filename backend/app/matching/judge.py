"""
Step 8, part 2: the LLM judge.

The rule score (scoring.py) can count skills and years, but it cannot READ: it doesn't know that
"rebuilt claims-processing APIs serving 2M requests/day" is strong evidence for a senior backend role.
The judge is an LLM that reads the role and one candidate's (anonymised) dossier, and returns, as JSON:
  - for every must-have: met yes / partly / no, with an exact quote from the resume as proof
  - up to 3 strengths, each with a quote; up to 3 gaps; a one-line summary; an overall rating

Same rule as Steps 5 and 7, "the LLM reads, code checks":
  - every quote is checked against the candidate's resume text; unverified quotes are flagged
  - a "yes" without a verified quote only counts as "partly"
  - the judge SCORE is computed by code from the must-have verdicts, not taken from the model
    (LLMs are poorly calibrated with numbers like 73/100)

Fairness: the dossier contains no name, email, phone, employee code, location or availability.
The judge only sees skills and experience; HR facts are handled by code.
"""
import logging
import re
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.extraction.postprocess import appears_in, normalize_for_match
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- what the LLM must return
class MustHaveVerdict(BaseModel):
    requirement: str
    met: Literal["yes", "partly", "no"]
    quote: str | None                     # exact words from the dossier, or null


class Strength(BaseModel):
    point: str
    quote: str


class JudgeVerdictLLM(BaseModel):
    must_haves: list[MustHaveVerdict]
    strengths: list[Strength] = Field(max_length=3)
    gaps: list[str] = Field(max_length=3)
    rating: Literal["strong", "good", "partial", "weak"]
    summary: str


JUDGE_SCHEMA = JudgeVerdictLLM.model_json_schema()

SYSTEM_PROMPT = """You are a careful technical reviewer helping staff an internal project.
You compare ONE candidate's resume extract with ONE project role and return JSON.

Rules:
1. Use ONLY the text inside <candidate>. Never assume skills or experience that are not written there.
2. "must_haves": one entry per must-have requirement, in the given order. "requirement": the name
   exactly as listed, without the years.
   "met": "yes" = clearly shown in real work; "partly" = related or only listed; "no" = not shown.
   "quote": the exact words from <candidate> that prove it (at most 15 words), or null if "no".
   Copy quotes from the resume's own sentences and bullet points, NOT from the "Total experience"
   or "Jobs" lines (those were written by software, not the person).
3. "strengths": up to 3 things that make this person a good fit, each with an exact quote (at most 15 words).
4. "gaps": up to 3 missing or weak points for THIS role (short phrases).
5. "rating": strong / good / partial / weak, for the role as a whole.
6. "summary": one sentence, no names, no pronouns like he/she.
7. Judge only skills and experience. Ignore names, gender, age, nationality and anything else
   about the person that is not about the work."""


# Lines our own code added to chunks (Steps 6-7): headers and the "Skills used:" line. Not resume text.
_GENERATED_LINE = re.compile(r"^(Experience \||Resume \(other sections\)|Profile$|Skills used:)")


def build_dossier(profile_lines: list[str], chunks: list[tuple[str, str]], max_chars: int) -> tuple[str, str]:
    """
    chunks = [(section, text)] in resume order. Facts from Step 5 first, then chunks until the size limit.
    Returns (dossier shown to the judge, evidence that quotes are checked against).

    The profile card (section "summary") is LEFT OUT: it is written from Step 5's LLM output, and in the
    first real run the judge quoted its paraphrases ("Adept in Java, Spring Boot, Kafka...") instead of the
    resume, so those quotes could never be verified. Chunk headers and "Skills used:" lines (written by our
    code) stay visible as orientation, but are not evidence.
    """
    dossier = "\n".join(profile_lines)
    evidence: list[str] = []
    for section, chunk in chunks:
        if section == "summary":
            continue
        # Chunk headers say "Employee EMP-1003 | ..." - the judge must not see who it is.
        clean = re.sub(r"Employee [A-Z]+-\d+ \| ", "", chunk)
        # Drop the "Skills used:" line our code adds for search (Step 7): in the second real run the judge
        # kept quoting it ("Skills used: Python, FastAPI...") instead of the resume, so Kavya got 3/8 verified.
        clean = "\n".join(l for l in clean.splitlines() if not l.startswith("Skills used:"))
        if len(dossier) + len(clean) + 2 > max_chars:
            break
        dossier += "\n\n" + clean
        evidence.append("\n".join(l for l in clean.splitlines() if not _GENERATED_LINE.match(l)))
    return dossier, "\n".join(evidence)


def build_messages(role_title: str, requirements: dict, dossier: str) -> list[dict[str, str]]:
    must = "\n".join(f"- {s['name']}" + (f" ({s['min_years']}+ years)" if s.get("min_years") else "")
                     for s in requirements.get("must_have", [])) or "- (none stated)"
    nice = ", ".join(s["name"] for s in requirements.get("nice_to_have", [])) or "(none)"
    years = requirements.get("min_total_years")
    role = (f"Role: {role_title}\n"
            f"Summary: {requirements.get('search_summary', '')}\n"
            f"Must-have requirements:\n{must}\n"
            f"Nice to have: {nice}\n"
            f"Minimum total experience: {f'{years} years' if years else 'not stated'}")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{role}\n\n<candidate>\n{dossier}\n</candidate>"},
    ]


class JudgeError(Exception):
    """The judge's answer could not be used."""


MET_VALUE = {"yes": 1.0, "partly": 0.5, "no": 0.0}


def _req_key(name: str) -> str:
    """'Python (5.0+ years)' -> 'python'  ·  'Django REST Framework' -> 'django rest framework'"""
    return normalize_for_match(re.sub(r"\(.*?\)", "", name or ""))


def verify(verdict: JudgeVerdictLLM, evidence_text: str, must_names: list[str]) -> dict:
    """Check every quote against the evidence the judge was given, and compute the judge score in code."""
    norm = normalize_for_match(evidence_text)

    def ok(quote: str | None) -> bool:
        return bool(quote) and appears_in(quote, norm)

    musts = []
    # Follow OUR list, not the model's. Match by name, ignoring case and anything in brackets: in the first
    # real run the model wrote "Python (5.0+ years)" for "Python", and every requirement looked unassessed.
    # If names still don't match but the counts do, fall back to position (rule 2 asks for the given order).
    by_name = {_req_key(v.requirement): v for v in verdict.must_haves}
    same_count = len(verdict.must_haves) == len(must_names)
    for i, name in enumerate(must_names):
        v = by_name.get(_req_key(name)) or (verdict.must_haves[i] if same_count else None)
        if v is None:
            musts.append({"requirement": name, "met": "no", "quote": None, "verified": False,
                          "note": "the judge did not assess this requirement"})
            continue
        verified = ok(v.quote)
        met = v.met
        if met == "yes" and not verified:
            met = "partly"                           # a claim without proof is only half a claim
        musts.append({"requirement": name, "met": met, "claimed": v.met, "quote": v.quote, "verified": verified})

    strengths = [{"point": s.point, "quote": s.quote, "verified": ok(s.quote)} for s in verdict.strengths]
    score = round(sum(MET_VALUE[m["met"]] for m in musts) / len(musts), 3) if musts else None
    return {
        "rating": verdict.rating,
        "summary": verdict.summary,
        "must_haves": musts,
        "strengths": strengths,
        "gaps": verdict.gaps,
        "judge_score": score,
        "quotes_verified": sum(m["verified"] for m in musts if m["quote"]) + sum(s["verified"] for s in strengths),
        "quotes_total": sum(1 for m in musts if m["quote"]) + len(strengths),
        "llm_output": verdict.model_dump(),          # exactly what the model said, for audit
    }


async def judge_candidate(ollama: OllamaClient, model: str, num_ctx: int, max_output_tokens: int,
                          role_title: str, requirements: dict, dossier: str, evidence: str) -> dict:
    started = time.perf_counter()
    data = await ollama.chat(build_messages(role_title, requirements, dossier), model=model, temperature=0.0,
                             num_ctx=num_ctx, json_schema=JUDGE_SCHEMA, num_predict=max_output_tokens)
    if data.get("done_reason") == "length":
        raise JudgeError(f"The judge's answer was cut off after {max_output_tokens} tokens.")
    try:
        verdict = JudgeVerdictLLM.model_validate_json(data["message"]["content"])
    except ValidationError as exc:
        raise JudgeError(f"The judge returned JSON that does not fit the schema: {exc}") from exc
    result = verify(verdict, evidence, [s["name"] for s in requirements.get("must_have", [])])
    result["stats"] = {
        "model": model,
        "seconds": round(time.perf_counter() - started, 1),
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
    }
    return result
