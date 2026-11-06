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
from app.extraction.skills import normalize_skill, spellings
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
   Copy quotes from the resume's own sentences and bullet points, NOT from the "Total experience",
   "Jobs", "Experience |" or "Project: ... | Role: ..." lines (those were written by software, not the person).
   A project's own bullet points are real work, just like a job's.
3. "strengths": up to 3 things that make this person a good fit, each with an exact quote (at most 15 words).
4. "gaps": up to 3 missing or weak points for THIS role (short phrases).
5. "rating": strong / good / partial / weak, for the role as a whole.
6. "summary": one sentence, no names, no pronouns like he/she.
7. Judge only skills and experience. Ignore names, gender, age, nationality and anything else
   about the person that is not about the work."""


# Lines our own code wrote into chunks (Steps 6-7, 13b): headers and skill/technology lists. Not resume text,
# so never evidence. Version 1 missed the project headers added in Step 13b ("Project: X | Role: ...",
# "Technologies: ..."): a quote from them would have counted as proof (found 2026-11-06).
_GENERATED_LINE = re.compile(
    r"^(Experience \||Project: |Resume \(other sections\)$|Profile$|Skills$|Education$|Certifications$|"
    r"Skills used:|Technologies:)"
)
# Generated lines the judge doesn't even see: in real runs it quoted them instead of the resume (Step 8).
_HIDDEN_LINE = re.compile(r"^(Skills used:|Technologies:)")


def _merge_parts(parts: list[str]) -> str:
    """
    One entry (a job, a project, a section) from its chunks, in order (small-to-big). Later chunks repeat the
    entry's header lines and the last lines of the previous chunk (the overlap); both are dropped.
    """
    merged = parts[0].splitlines()
    # The header our code wrote on every part: the first line ("Employee EMP-… | Experience | …") and, if
    # present, the "Skills used:" / "Technologies:" line right after it.
    header = merged[:1] + [l for l in merged[1:2] if _HIDDEN_LINE.match(l)]
    for part in parts[1:]:
        lines = part.splitlines()
        while lines and header and lines[0] in header:
            lines = lines[1:]
        overlap = 0
        for k in range(min(len(lines), len(merged), 12), 0, -1):    # longest repeated run of lines
            if merged[-k:] == lines[:k]:
                overlap = k
                break
        merged.extend(lines[overlap:])
    return "\n".join(merged)


def assemble_entries(chunks: list[tuple]) -> list[tuple[str, str, str]]:
    """
    chunks = [(section, text)] or [(section, text, meta)] in resume order -> [(entry key, section, text)].
    Chunks with the same meta["entry"] (the parts of one job or project) become ONE entry. Chunks without
    meta (indexed before Step 13b part 3) stay one entry each, as before.
    """
    entries: dict[str, list] = {}
    order: list[str] = []
    for i, chunk in enumerate(chunks):
        section, text = chunk[0], chunk[1]
        meta = chunk[2] if len(chunk) > 2 and chunk[2] else {}
        key = meta.get("entry") or f"chunk-{i}"
        if key not in entries:
            entries[key] = [section, []]
            order.append(key)
        entries[key][1].append(text)
    return [(key, entries[key][0], _merge_parts(entries[key][1])) for key in order]


def _relevance(text: str, terms: list[str], strong: set[str]) -> int:
    """How many of the role's skills an entry mentions: must-haves count 2, nice-to-haves 1."""
    norm = normalize_for_match(text)
    score = 0
    for term in terms:
        for spelling in normalize_skill(term)[:1] and spellings(normalize_skill(term)[0]) or [term]:
            t = normalize_for_match(spelling)
            if t and re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", norm):
                score += 2 if term in strong else 1
                break
    return score


def build_dossier(profile_lines: list[str], chunks: list[tuple], max_chars: int,
                  must_terms: list[str] | None = None, nice_terms: list[str] | None = None) -> tuple[str, str]:
    """
    chunks = [(section, text[, meta])] in resume order. Facts from Step 5 first, then whole entries (jobs,
    projects, sections) until the size limit. Returns (dossier shown to the judge, evidence for quotes).

    Small-to-big (2026-11-06): the chunks of one job or project are joined back into the whole entry, so the
    judge reads a long job as one piece. When everything doesn't fit, the entries that mention the role's
    skills most are chosen first (then shown in resume order). Before, chunks were added in resume order until
    the limit, so on a long resume the projects at the end were cut off however relevant they were.

    The profile card (section "summary") is LEFT OUT: it is written from extracted data, and in the first real
    run the judge quoted its paraphrases instead of the resume, so those quotes could never be verified.
    Chunk headers stay visible as orientation, but are never evidence (_GENERATED_LINE).
    """
    entries = []
    for key, section, text in assemble_entries(chunks):
        if section == "summary":
            continue
        # Chunk headers say "Employee EMP-1003 | ..." - the judge must not see who it is.
        clean = re.sub(r"Employee [A-Z]+-\d+ \| ", "", text)
        # Lines our code writes for search (Step 7): the judge quoted them instead of the resume.
        clean = "\n".join(l for l in clean.splitlines() if not _HIDDEN_LINE.match(l))
        entries.append((key, clean))

    must_terms, nice_terms = must_terms or [], nice_terms or []
    budget = max_chars - len("\n".join(profile_lines))
    chosen: set[str] = set()
    if sum(len(c) + 2 for _, c in entries) <= budget:
        chosen = {k for k, _ in entries}
    else:
        strong = set(must_terms)
        ranked = sorted(enumerate(entries),
                        key=lambda pair: (-_relevance(pair[1][1], must_terms + nice_terms, strong), pair[0]))
        used = 0
        for _, (key, clean) in ranked:
            if used + len(clean) + 2 <= budget:
                chosen.add(key)
                used += len(clean) + 2

    dossier = "\n".join(profile_lines)
    evidence: list[str] = []
    for key, clean in entries:                       # chosen entries, in resume order
        if key not in chosen:
            continue
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
