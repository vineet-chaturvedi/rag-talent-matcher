"""
Chunking: cut one resume into small, self-contained pieces for semantic search.

Why chunks instead of one vector per resume? One vector for a whole resume is an AVERAGE of
everything in it - a DevOps job, a Java job, education - and matches nothing sharply.
A chunk is about ONE thing (one job, the profile, the rest), so its vector is precise.

Each resume becomes:
  1. a PROFILE CARD   - headline, total years, summary, skills with years   (from Step 5)
  2. one EXPERIENCE chunk per job - that job's ORIGINAL text from the resume  (nothing lost)
  3. OTHER chunk(s)   - everything else: profile text, skills section, education, certifications

Every chunk starts with a short header ("Employee EMP-1003 | Experience | ...") so it still makes
sense on its own - when it is retrieved alone, and to the embedding model.

Pure functions only: no database, no Ollama. Easy to read and to test.
"""
import re
from dataclasses import dataclass
from datetime import date

from app.db.enums import ChunkSection
from app.extraction.postprocess import ground_job_skills, normalize_for_match

_HEADING = re.compile(
    r"^(education|certifications?|skills|technical skills|key skills|projects|summary|profile|"
    r"professional summary|contact|languages|awards|achievements|interests|hobbies|references|"
    r"experience|work experience|professional experience|employment history)\s*:?$",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s()-]{8,}\d")
# Gendered words -> neutral ones. Matching must not see (or be influenced by) gender.
_PRONOUNS = {"she": "they", "he": "they", "her": "their", "his": "their", "him": "them",
             "hers": "theirs", "herself": "themselves", "himself": "themselves"}
_PRONOUN_RE = re.compile(r"\b(" + "|".join(_PRONOUNS) + r")\b", re.IGNORECASE)


@dataclass
class JobInfo:
    title: str | None
    company: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    description: str | None


@dataclass
class ChunkDraft:
    section: ChunkSection
    text: str          # header + body: exactly what is embedded, stored and shown

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text) // 4)   # rule of thumb from Step 1: ~4 characters per token


# --------------------------------------------------------------------------- helpers
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#.]+", " ", (text or "").lower())).strip()


def _neutral_pronoun(match: re.Match) -> str:
    word = match.group(0)
    neutral = _PRONOUNS[word.lower()]
    return neutral.capitalize() if word[0].isupper() else neutral


def anonymize(text: str, full_name: str | None) -> str:
    """
    Remove what identifies the person but says nothing about their skills: name, email, phone,
    and gendered pronouns ("She specialises" -> "They specialises": slightly odd grammar, but neutral).
    Matching (and the LLM judge in Step 8) should look at experience, never at identity.
    """
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    text = _PRONOUN_RE.sub(_neutral_pronoun, text)
    if full_name:
        parts = [full_name] + [p for p in full_name.split() if len(p) >= 3]
        for part in parts:
            text = re.sub(rf"\b{re.escape(part)}\b", "[name]", text, flags=re.IGNORECASE)
    return text


def split_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """
    Split at line boundaries into pieces of at most max_chars. Each new piece repeats the last
    ~overlap characters of the previous one, so a sentence cut at the border is still whole somewhere.
    """
    lines = [l for l in text.split("\n") if l.strip()]
    pieces: list[str] = []
    current: list[str] = []
    for line in lines:
        while len(line) > max_chars:                 # a single enormous line: hard cut
            lines_left = line[max_chars:]
            line_part = line[:max_chars]
            if current:
                pieces.append("\n".join(current))
                current = []
            pieces.append(line_part)
            line = lines_left
        if current and len("\n".join(current + [line])) > max_chars:
            pieces.append("\n".join(current))
            tail: list[str] = []                     # carry the last lines over as overlap
            for prev in reversed(current):
                if len("\n".join([prev] + tail)) > overlap:
                    break
                tail.insert(0, prev)
            current = tail
        current.append(line)
    if current:
        pieces.append("\n".join(current))
    return pieces


def _period(job: JobInfo) -> str:
    # Years only: a resume that says just "2018" is stored as 1 Jan 2018, so months would mislead here.
    start = str(job.start_date.year) if job.start_date else "?"
    end = "present" if job.is_current else (str(job.end_date.year) if job.end_date else "?")
    return f"{start} - {end}"


def _find_job_lines(jobs: list[JobInfo], lines: list[str]) -> list[int | None]:
    """The line where each job's entry starts: title and company on the same or neighbouring lines."""
    normed = [_norm(l) for l in lines]
    starts: list[int | None] = []
    cursor = 0
    for job in jobs:
        t, c = _norm(job.title or ""), _norm(job.company or "")
        found = None
        for begin in dict.fromkeys((cursor, 0)):
            for i in range(begin, len(lines)):
                around = " ".join(normed[max(0, i - 1): i + 2])
                if c and c in normed[i] and (not t or t in around):
                    found = i
                    break
                if t and t in normed[i] and c and c in around:
                    found = i
                    break
            if found is None and c:                  # fallback: the company line alone
                found = next((i for i in range(begin, len(lines)) if c in normed[i]), None)
            if found is not None:
                break
        starts.append(found)
        if found is not None:
            cursor = found + 1
    return starts


# --------------------------------------------------------------------------- main function
def build_chunks(
    *,
    employee_code: str,
    full_name: str | None,
    raw_text: str,
    headline: str | None,
    total_years: float | None,
    summary: str | None,
    skills: list[tuple[str, float | None]],
    jobs: list[JobInfo],
    max_chars: int,
    overlap: int,
    anonymize_text: bool = True,
) -> list[ChunkDraft]:
    clean = (lambda t: anonymize(t, full_name)) if anonymize_text else (lambda t: t)
    chunks: list[ChunkDraft] = []
    skill_names = [name for name, _years in skills]

    # ---- 1. Profile card (from the Step 5 structured data)
    card = [f"Employee {employee_code} | Profile"]
    if headline or total_years is not None:
        years = f" with {total_years} years of total experience" if total_years is not None else ""
        card.append(f"{headline or 'Professional'}{years}.")
    if summary:
        card.append(summary)
    if skills:
        card.append("Skills: " + ", ".join(f"{n} ({y} years)" if y else n for n, y in skills))
    if len(card) > 1:
        chunks.append(ChunkDraft(ChunkSection.SUMMARY, clean("\n".join(card))[: max_chars * 2]))

    # ---- 2. One chunk per job, using the job's ORIGINAL text
    lines = raw_text.split("\n")
    starts = _find_job_lines(jobs, lines)
    found_starts = sorted(s for s in starts if s is not None)
    used: set[int] = set()
    for job, start in zip(jobs, starts):
        header = f"Employee {employee_code} | Experience | {job.title or 'Role'} at {job.company or 'unknown'} ({_period(job)})"
        if start is None:
            body = job.description or ""          # couldn't locate it: fall back to the Step 5 summary
        else:
            end = next((s for s in found_starts if s > start), len(lines))
            end = min(end, start + 40)
            for i in range(start + 1, end):       # stop early at a section heading (EDUCATION, SKILLS...)
                if _HEADING.match(lines[i].strip()):
                    end = i
                    break
            used.update(range(start, end))
            body = "\n".join(lines[start:end])
        # Enrichment (Step 7): list the skills written in this job's text, by their CANONICAL names.
        # The resume may say "k8s"; the chunk now also says "Kubernetes", which the embedding
        # model and keyword search both understand. Short job chunks gain real content too.
        job_skills, _ = ground_job_skills(skill_names, normalize_for_match(body))
        if job_skills:
            header = f"{header}\nSkills used: {', '.join(job_skills)}"
        for piece in split_text(clean(body), max_chars - len(header) - 1, overlap) or [""]:
            if piece.strip():
                chunks.append(ChunkDraft(ChunkSection.EXPERIENCE, f"{header}\n{piece}"))

    # ---- 3. Everything else, so nothing from the resume is lost
    rest = "\n".join(l for i, l in enumerate(lines) if i not in used and l.strip())
    header = f"Employee {employee_code} | Resume (other sections)"
    for piece in split_text(clean(rest), max_chars - len(header) - 1, overlap):
        if len(piece.strip()) >= 20:
            chunks.append(ChunkDraft(ChunkSection.OTHER, f"{header}\n{piece}"))

    return chunks
