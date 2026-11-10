"""
Who counts as a candidate at all (shared by match runs and the agent's find_candidates).

The rule: a person must have AT LEAST ONE of the role's must-have skills: as a skill on their profile
(directly or through a related skill, e.g. WooCommerce -> WordPress), or named in their resume text.

Why: retrieval fuses three signals, and the meaning (vector) and keyword searches always find SOMEONE. For a
"WordPress developer" they find web developers with neither WordPress nor PHP. Ranked, scored at 0.00 and
sent to the LLM judge, those people waste minutes of model time and the reviewer's attention (seen
2026-11-06: Ananya Iyer at #2 for a WordPress role). So they are left out before scoring and judging, and the
run records how many were left out.

The text check: a skill the catalogue knows is found with the extraction rules (all spellings, "WP" for
WordPress, short common words like "Go" only when capitalised), so it only catches resumes extracted before
the catalogue learned the skill. Any other skill: the term as a whole word.
"""
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Resume
from app.extraction.postprocess import normalize_for_match
from app.extraction.skills import find_skills, is_known, normalize_skill

# Retrieve a wider pool than asked for, so people WITH the skills are not crowded out by people the meaning
# search finds similar but who have none of them (those are removed afterwards).
POOL_FACTOR, MIN_POOL = 4, 20


def pool_size(top_k: int) -> int:
    return max(top_k * POOL_FACTOR, MIN_POOL)


def mentions(text: str, skill: str) -> bool:
    """Does the resume text name this skill? (see the module docstring)"""
    names = normalize_skill(skill)
    if names and is_known(names[0]):
        return names[0] in {canonical for canonical, _, _ in find_skills(text)}
    term = normalize_for_match(skill)
    return bool(term) and re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",
                                    normalize_for_match(text)) is not None


@dataclass
class Eligibility:
    kept: list = field(default_factory=list)            # candidates with at least one must-have
    named_in_text: dict[int, list[str]] = field(default_factory=dict)   # resume_id -> must-haves found only in text
    excluded: int = 0                                     # came up in search, but have none of the must-haves


async def keep_qualified(session: AsyncSession, candidates: list, must_have: list[str]) -> Eligibility:
    """Split retrieval's candidates into the qualified ones (in their order) and a count of the rest."""
    result = Eligibility()
    if not must_have:                       # a role without must-haves: everyone found is a candidate
        result.kept = list(candidates)
        return result
    texts = dict((await session.execute(
        select(Resume.id, Resume.raw_text).where(Resume.id.in_([c.resume_id for c in candidates if c.must_missing]))
    )).all()) if candidates else {}
    for c in candidates:
        named = [s for s in c.must_missing if mentions(texts.get(c.resume_id) or "", s)]
        if named:
            result.named_in_text[c.resume_id] = named
        if c.must_matched or named:
            result.kept.append(c)
        else:
            result.excluded += 1
    return result
