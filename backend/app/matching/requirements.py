"""
Role parsing: a project role written in plain language -> structured requirements.

    "Platform engineer to migrate 60 services to Kubernetes on AWS. Must have hands-on Kubernetes,
     Terraform, CI/CD and AWS. Nice to have: Helm, ArgoCD, Prometheus/Grafana..."
                                   │ LLM (once per role, ~30-60 s)
                                   ▼
    must_have: Kubernetes, Terraform, CI/CD, AWS · nice_to_have: Helm, ArgoCD, Prometheus, Grafana
    search_summary: "Platform engineer with production Kubernetes on AWS, Terraform, CI/CD ..."

Same rule as resume extraction: the LLM reads and labels; code normalises skill names.
The result is stored on the role and shown to the resource manager, who can correct it.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.extraction.postprocess import contains_phrase, normalize_for_match
from app.extraction.skills import CATALOG, normalize_skill, skills_in_phrase
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- what the LLM must return
class RequiredSkillLLM(BaseModel):
    name: str
    min_years: float | None


class RoleRequirementsLLM(BaseModel):
    seniority: Literal["junior", "mid", "senior", "lead", "principal", "unspecified"]
    must_have: list[RequiredSkillLLM]
    nice_to_have: list[RequiredSkillLLM]
    min_total_years: float | None
    location: str | None
    domain: list[str]                 # business areas: "insurance", "payments", "retail"...
    search_summary: str               # 2-3 sentences describing the ideal person (used for vector search)


ROLE_SCHEMA = RoleRequirementsLLM.model_json_schema()

_KNOWN_SKILLS = ", ".join(CATALOG)    # the canonical names, so the model can map descriptions to them

SYSTEM_PROMPT = f"""You turn a project role description into structured requirements (JSON).

Rules:
1. Use ONLY what the description says. Do not invent requirements.
2. "must_have": skills the description says are required / must have / strong / essential.
   "nice_to_have": skills described as nice to have / a plus / preferred / bonus.
3. Use these canonical skill names whenever one fits, also when the description paraphrases a skill
   (e.g. "container orchestration" -> "Kubernetes", "CI/CD pipelines" -> "CI/CD"). Never guess a
   specific tool the description does not point to:
   {_KNOWN_SKILLS}
   If a required skill is not in the list, write it as stated.
   One skill per item, as a short name: split "RAG using vector databases" into "RAG" and
   "Vector Databases"; write "NLP", not "NLP fundamentals".
4. "min_years": only if the description gives years for that skill, else null.
   "min_total_years": overall years of experience if stated, else null.
5. "location": the work location if stated, else null. "domain": business domains mentioned (lowercase).
6. "search_summary": 2-3 sentences describing the ideal person's experience, using the role's own
   key terms. No names."""


def build_messages(title: str, description: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Role title: {title}\n\n<role_description>\n{description}\n</role_description>"},
    ]


class RoleParseError(Exception):
    """The model's answer could not be used."""


# --------------------------------------------------------------------------- normalisation (plain Python)
def canonical_skills(raw: str) -> list[str]:
    """
    A requirement as written -> canonical skill names.
      "k8s"                                           -> ["Kubernetes"]           (catalog spelling)
      "retrieval-augmented generation using vector databases" -> ["RAG", "Vector Databases"]
      "nlp fundamentals"                              -> ["NLP"]                  (known skill inside)
      "Bicep"                                         -> ["Bicep"]                (unknown: kept)
    """
    names = normalize_skill(raw)
    out: list[str] = []
    for name in names:
        expanded = [name] if name in CATALOG else (skills_in_phrase(name) or [name])
        out.extend(n for n in expanded if n not in out)
    return out


def normalise_skill_list(items: list[dict]) -> list[dict]:
    """Normalise names, split compound phrases, merge duplicates (case-insensitive). Used for LLM output,
    for edits by a person (PUT) and again at search time, so older stored requirements benefit too."""
    out: dict[str, dict] = {}
    for item in items:
        written = item.get("as_written") or item["name"]
        for i, name in enumerate(canonical_skills(item["name"])):
            key = name.lower()
            if key not in out:
                out[key] = {"name": name, "min_years": item.get("min_years") if i == 0 else None,
                            "as_written": written}
            elif out[key]["min_years"] is None and i == 0:
                out[key]["min_years"] = item.get("min_years")
    return list(out.values())


def normalise_skill_sections(requirements: dict) -> dict:
    """must_have / nice_to_have normalised; a skill in both lists stays must-have only."""
    must = normalise_skill_list(requirements.get("must_have", []))
    must_names = {s["name"].lower() for s in must}
    nice = [s for s in normalise_skill_list(requirements.get("nice_to_have", [])) if s["name"].lower() not in must_names]
    return {**requirements, "must_have": must, "nice_to_have": nice}


_SENIORITY_WORDS = {
    "junior": ["junior", "jr", "entry level", "graduate"],
    "mid": ["mid level", "intermediate"],              # not plain "mid": it matches "start mid-November"
    "senior": ["senior", "sr"], "lead": ["lead", "tech lead", "team lead"], "principal": ["principal", "staff"],
}
_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


def ground_in_description(requirements: dict, title: str, description: str) -> dict:
    """
    "The LLM reads, code checks" for the role side. Measured in Step 7: the 7B model invented
    "Kubernetes 3 years, AWS 3 years, 5 years total" for a description that names no years at all.
      - a number of years is kept only if that number is written next to "years" in the text
      - a domain is kept only if the word appears in the title or description
      - a seniority level is kept only if one of its words appears there (Step 8)
    """
    text = f"{title}\n{description}"
    stated = {float(n) for n in _YEARS.findall(text)}
    norm = normalize_for_match(text)

    def keep(value):
        return value if value is not None and float(value) in stated else None

    out = dict(requirements)
    for section in ("must_have", "nice_to_have"):
        out[section] = [{**item, "min_years": keep(item.get("min_years"))} for item in requirements.get(section, [])]
    out["min_total_years"] = keep(requirements.get("min_total_years"))
    out["domain"] = [d for d in requirements.get("domain", []) if contains_phrase(norm, d)]
    seniority = requirements.get("seniority") or "unspecified"
    if seniority != "unspecified" and not any(contains_phrase(norm, w) for w in _SENIORITY_WORDS.get(seniority, [])):
        out["seniority"] = "unspecified"            # Step 8: "mid" was invented for a role that never says it
    return out


def effective_requirements(role) -> dict:
    """The requirements exactly as matching uses them: normalised, and grounded unless a person edited them."""
    req = normalise_skill_sections(role.requirements or {})
    return req if req.get("edited_by_user") else ground_in_description(req, role.title, role.description)


def normalise_requirements(llm: RoleRequirementsLLM, title: str, model: str, description: str = "") -> dict:
    skills = normalise_skill_sections({
        "must_have": [{"name": s.name, "min_years": s.min_years} for s in llm.must_have],
        "nice_to_have": [{"name": s.name, "min_years": s.min_years} for s in llm.nice_to_have],
    })
    requirements = {
        "title": title,
        "seniority": llm.seniority,
        "must_have": skills["must_have"],
        "nice_to_have": skills["nice_to_have"],
        "min_total_years": llm.min_total_years,
        "location": llm.location,
        "domain": sorted({d.strip().lower() for d in llm.domain if d.strip()}),
        "search_summary": llm.search_summary.strip(),
        "parsed_by": model,
        "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "edited_by_user": False,
    }
    return ground_in_description(requirements, title, description)


# --------------------------------------------------------------------------- the LLM call
async def parse_role(ollama: OllamaClient, title: str, description: str, model: str, num_ctx: int) -> dict:
    data = await ollama.chat(
        build_messages(title, description), model=model, temperature=0.0,
        num_ctx=num_ctx, json_schema=ROLE_SCHEMA, num_predict=1024,
    )
    if data.get("done_reason") == "length":
        raise RoleParseError("The model's answer was cut off.")
    try:
        llm = RoleRequirementsLLM.model_validate_json(data["message"]["content"])
    except ValidationError as exc:
        raise RoleParseError(f"The model returned JSON that does not fit the schema: {exc}") from exc
    requirements = normalise_requirements(llm, title, model, description)
    logger.info("Parsed role '%s' with %s: %d must-have, %d nice-to-have",
                title, model, len(requirements["must_have"]), len(requirements["nice_to_have"]))
    return requirements


def search_terms(requirements: dict) -> list[str]:
    """Words for KEYWORD search: every known spelling of every required skill, plus domains."""
    from app.extraction.skills import spellings
    terms: list[str] = []
    for skill in requirements.get("must_have", []) + requirements.get("nice_to_have", []):
        terms.extend(spellings(skill["name"]))
    terms.extend(requirements.get("domain", []))
    return terms


def vector_query(requirements: dict) -> str:
    """Text for SEMANTIC search: the ideal-person summary plus the must-have skills."""
    must = ", ".join(s["name"] for s in requirements.get("must_have", []))
    return f"{requirements.get('search_summary', '')} Key skills: {must}".strip()
