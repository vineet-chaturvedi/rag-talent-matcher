"""
Chunking: cut one resume into small, self-contained pieces for semantic search.

Why chunks instead of one vector per resume? One vector for a whole resume is an AVERAGE of
everything in it - a DevOps job, a Java job, education - and matches nothing sharply.
A chunk is about ONE thing (one job, the profile, the rest), so its vector is precise.

Each resume becomes:
  1. a PROFILE CARD   - headline, total years, skills with years or uses: facts computed by code, labelled
  2. one EXPERIENCE chunk per job     - that job's ORIGINAL text, up to the next job or section heading
  3. one PROJECT chunk per project    - its ORIGINAL text, with its role and technologies (doc 18)
  4. SKILLS / EDUCATION / OTHER chunks - the rest, section by section, so nothing is lost

Sections are found by app/extraction/sections.py, the same code extraction uses. Version 1 knew only a few
heading words, so a "KEY PROJECTS" section was glued onto the job above it (doc 07 audit).

Every chunk starts with a short header ("Employee EMP-1003 | Experience | ...") so it still makes
sense on its own - when it is retrieved alone, and to the embedding model.

Pure functions only: no database, no Ollama. Easy to read and to test.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from app.db.enums import ChunkSection
from app.extraction import sections as sec
from app.extraction.postprocess import (
    entry_blocks, find_entry_line, ground_job_skills, name_keys, normalize_for_match,
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
class ProjectInfo:
    name: str
    role: str | None
    duration_text: str | None
    technologies: list[str]
    company: str | None


@dataclass
class ChunkDraft:
    section: ChunkSection
    text: str          # header + body: exactly what is embedded, stored and shown
    # Structured facts about the chunk, stored as real fields (not only inside the text), so search can filter
    # on them and the judge can rebuild a whole job or project from its pieces ("small-to-big"):
    #   entry       which entry it belongs to: "profile", "job-0", "project-3", "section-2" (the parent id)
    #   entry_type  profile / job / project / section
    #   entry_name  "Senior SE at Encoresky", "Finexity", "Technical Skills"
    #   role, technologies (comma-separated), part (0, 1, 2 ... when an entry is split)
    meta: dict = field(default_factory=dict)

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
        # Case-sensitive, as written ("Harsh", "HARSH"): a first name can also be an ordinary word
        # ("harsh conditions"), which must stay (doc 18, P12).
        parts = [full_name] + [p.strip(".") for p in full_name.split() if len(p.strip(".")) >= 3]
        for part in parts:
            for form in {part, part.upper(), part.title()}:
                text = re.sub(rf"\b{re.escape(form)}\b", "[name]", text)
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
        while len(line) > max_chars:                 # a single enormous line: cut it, at a space if possible
            cut = line.rfind(" ", max_chars // 2, max_chars)
            cut = cut if cut > 0 else max_chars       # (never in the middle of a word when there is a space)
            lines_left = line[cut:].lstrip()
            line_part = line[:cut].rstrip()
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


_SECTION_CHUNK = {sec.SKILLS: ChunkSection.SKILLS, sec.EDUCATION: ChunkSection.EDUCATION,
                  sec.CERTIFICATIONS: ChunkSection.CERTIFICATION}
_SECTION_LABEL = {sec.SKILLS: "Skills", sec.EDUCATION: "Education", sec.CERTIFICATIONS: "Certifications"}


# --------------------------------------------------------------------------- main function
def build_chunks(
    *,
    employee_code: str,
    full_name: str | None,
    raw_text: str,
    headline: str | None,
    total_years: float | None,
    summary: str | None,             # kept for callers; no longer put in the card (model-written)
    skills: list[tuple],             # (name, years) or (name, years, uses) or (name, years, uses, years_basis)
    jobs: list[JobInfo],
    max_chars: int,
    overlap: int,
    anonymize_text: bool = True,
    projects: list[ProjectInfo] | None = None,
    experience_basis: str | None = None,
) -> list[ChunkDraft]:
    clean = (lambda t: anonymize(t, full_name)) if anonymize_text else (lambda t: t)
    chunks: list[ChunkDraft] = []
    projects = projects or []
    skill_rows = [(s[0], s[1], s[2] if len(s) > 2 else 0, s[3] if len(s) > 3 else None) for s in skills]
    skill_names = [row[0] for row in skill_rows]

    def add(section: ChunkSection, header: str, body: str, meta: dict) -> None:
        pieces = [p for p in split_text(clean(body), max_chars - len(header) - 1, overlap) if p.strip()]
        for part, piece in enumerate(pieces):
            chunks.append(ChunkDraft(section, f"{header}\n{piece}", {**meta, "part": part}))

    # ---- 1. Profile card: facts our CODE computed from the structured profile, labelled as such.
    # No model-written summary in it (it is a paraphrase and can drift from the resume); the resume's own
    # summary section is indexed as its own chunk below.
    card = [f"Employee {employee_code} | Profile (generated from the extracted data, not resume text)"]
    if headline or total_years is not None:
        stated = " (as stated in the resume)" if experience_basis == "stated in resume" else ""
        years = f" with {total_years} years of total experience{stated}" if total_years is not None else ""
        card.append(f"{headline or 'Professional'}{years}.")
    if skill_rows:
        def label(name: str, years: float | None, uses: int, basis: str | None) -> str:
            if years:
                return f"{name} (about {years} years)" if basis == "estimated" else f"{name} ({years} years)"
            return f"{name} (used in {uses} projects)" if uses > 1 else name
        card.append("Skills: " + ", ".join(label(*row) for row in skill_rows))
    if len(card) > 1:
        chunks.append(ChunkDraft(ChunkSection.SUMMARY, clean("\n".join(card))[: max_chars * 2],
                                 {"entry": "profile", "entry_type": "profile", "entry_name": "Profile", "part": 0}))

    # ---- 2. Where everything is: sections, job entries, project entries (same rules as extraction)
    lines, sections = sec.split_sections(raw_text)
    normed = [_norm(line) for line in lines]
    ranges = lambda *kinds: [(s.heading_line or s.start, s.end) for s in sections if s.kind in kinds]  # noqa: E731
    taken: set[int] = set()
    job_starts, cursor = [], 0
    for job in jobs:
        company, title = _norm(job.company or "")[:40], _norm(job.title or "")[:40]
        pos = None
        for keys in ([company, title], [company], [title]):
            if all(keys) and pos is None:
                pos = find_entry_line(keys, normed, ranges(sec.EXPERIENCE), taken, cursor)
        if pos is not None:
            taken.add(pos)
            cursor = pos + 1
        job_starts.append(pos)
    project_starts, cursor = [], 0
    for project in projects:
        pos = find_entry_line(name_keys(project.name), normed, ranges(sec.PROJECTS, sec.EXPERIENCE), taken, cursor)
        if pos is not None:
            taken.add(pos)
            cursor = pos + 1
        project_starts.append(pos)
    blocks = entry_blocks(job_starts + project_starts, sections, len(lines))
    job_blocks, project_blocks = blocks[:len(jobs)], blocks[len(jobs):]
    used: set[int] = set()

    # ---- 3. One chunk per job (its own text), with the skills written in it
    for job_number, (job, block) in enumerate(zip(jobs, job_blocks)):
        header = f"Employee {employee_code} | Experience | {job.title or 'Role'} at {job.company or 'unknown'} ({_period(job)})"
        if block is None:
            # Couldn't locate it in the text: fall back to the model's one-sentence description, labelled.
            body = f"(Description written by the extraction model) {job.description}" if job.description else ""
        else:
            used.update(range(*block))
            body = "\n".join(lines[block[0]:block[1]])
        # Enrichment (Step 7): the skills written in this job's text, by their CANONICAL names
        # ("k8s" -> "Kubernetes"), which the embedding model and keyword search both understand.
        job_skills, _ = ground_job_skills(skill_names, normalize_for_match(body))
        if job_skills:
            header = f"{header}\nSkills used: {', '.join(job_skills)}"
        add(ChunkSection.EXPERIENCE, header, body, {
            "entry": f"job-{job_number}", "entry_type": "job",
            "entry_name": f"{job.title or 'Role'} at {job.company or 'unknown'}", "role": job.title or "",
            "technologies": ", ".join(job_skills),
        })

    # ---- 4. One chunk per project, with its role and technologies (doc 18)
    for project_number, (project, block) in enumerate(zip(projects, project_blocks)):
        if block is None:
            continue
        used.update(range(*block))
        facts = [f"Project: {project.name}"]
        if project.role:
            facts.append(f"Role: {project.role}")
        if project.duration_text:
            facts.append(project.duration_text)
        if project.company:
            facts.append(f"at {project.company}")
        header = f"Employee {employee_code} | " + " | ".join(facts)
        if project.technologies:
            header = f"{header}\nTechnologies: {', '.join(project.technologies)}"
        add(ChunkSection.PROJECT, header, "\n".join(lines[block[0]:block[1]]), {
            "entry": f"project-{project_number}", "entry_type": "project", "entry_name": project.name,
            "role": project.role or "", "technologies": ", ".join(project.technologies),
        })

    # ---- 5. The rest, section by section, so nothing from the resume is lost
    for number, s in enumerate(sections):
        start = s.heading_line if s.heading_line is not None else s.start
        body = [lines[i] for i in range(s.start, s.end) if i not in used and lines[i].strip()]
        if len("\n".join(body).strip()) < 20:
            continue                                  # nothing left under this heading (e.g. all in job chunks)
        rest = "\n".join(([lines[start]] if s.heading_line is not None else []) + body)
        section = _SECTION_CHUNK.get(s.kind, ChunkSection.OTHER)
        label = _SECTION_LABEL.get(s.kind, "Resume (other sections)")
        add(section, f"Employee {employee_code} | {label}", rest, {
            "entry": f"section-{number}", "entry_type": "section", "entry_name": s.heading or "Header",
        })

    return chunks
