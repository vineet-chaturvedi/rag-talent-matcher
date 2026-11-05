"""
From the LLM's structure + the resume text to a clean, checked profile, all in plain Python.

  1. Sections        split the text: summary, skills, experience, projects, education ...   (sections.py)
  2. Jobs            parse dates; find each job's own lines in the text
  3. Projects        find each project's own lines; its technologies are checked against those lines
  4. Skills          a dictionary scan of the WHOLE text (skills.py) plus the items of skills lists;
                     every mention is placed: in a job, in a project, in a skills list, or only claimed
  5. Years           per skill, from the dated jobs that use it (also implied use: Laravel -> PHP), never
                     more than the technology has existed (RAG: since 2020)
  6. Total years     from dated jobs; when a resume has none (7 of 9 real resumes), the stated "6+ years"

Version 2 (doc 18). Version 1 trusted the model's skill lists; on real resumes that stored headings as skills,
lost listed skills, and gave 5.2 years of PHP to a 13-year PHP developer.
"""
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher

from app.extraction.dates import interval, months_to_years, parse_range, total_months
from app.extraction.schema import ResumeExtraction
from app.extraction.sections import (
    EXPERIENCE, HEADER, PROJECTS, RESPONSIBILITIES, SKILLS, SUMMARY, Section, section_at, split_sections,
)
from app.extraction.skills import (
    TECH_SINCE, category_of, find_skills, is_known, normalize_skill, skills_in_phrase, spellings,
    with_implied_use,
)


@dataclass
class ProfileSkill:
    name: str
    category: str | None
    years: float | None          # None = no dated job shows it (listed, or used in undated projects)
    last_used_year: int | None
    evidence: str | None         # a line from the resume
    uses: int = 0                # jobs + projects in which it was used
    source: str = "mentioned"    # where the strongest evidence is: job / project / skills list / mentioned


@dataclass
class ProfileJob:
    title: str | None
    company: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    months: int | None
    description: str | None
    skills: list[str]


@dataclass
class ProfileProject:
    name: str
    role: str | None
    duration_text: str | None
    duration_months: int | None
    technologies: list[str]
    description: str | None
    link: str | None
    job_index: int | None        # the job it belongs to (index into Profile.jobs), if known
    job_basis: str | None        # "inside job" (written under it) / "only employer" (assumed) / None


@dataclass
class Profile:
    headline: str | None
    summary: str | None
    total_experience_years: float | None
    jobs: list[ProfileJob]
    skills: list[ProfileSkill]
    education: list[dict]
    certifications: list[str]
    projects: list[ProfileProject] = field(default_factory=list)
    experience_basis: str | None = None       # "dated jobs" / "stated in resume" / None
    stated_years: float | None = None         # "6+ years" written in the resume
    rejected_skills: list[dict] = field(default_factory=list)   # what we threw away, and why
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- text matching helpers
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#.]+", " ", (text or "").lower())).strip()


normalize_for_match = _norm   # public name, used by chunking and the judge


def appears_in(snippet: str | None, text_norm: str, min_ratio: float = 0.8) -> bool:
    """Does the snippet really occur in the resume? Exact match, or a near-exact one (small LLM copy slips)."""
    if not snippet:
        return False
    s = _norm(snippet)
    if not s:
        return False
    if s in text_norm:
        return True
    match = SequenceMatcher(None, text_norm, s, autojunk=False).find_longest_match(0, len(text_norm), 0, len(s))
    return match.size / len(s) >= min_ratio


def contains_phrase(text_norm: str, phrase: str) -> bool:
    """Whole-word match: 'go' must not match inside 'google', 'java' not inside 'javascript'."""
    p = _norm(phrase)
    return bool(p) and re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", text_norm) is not None


_STATED_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:yrs?|years?)\b(?!\s*(?:old|of age))", re.IGNORECASE)
# A duration written next to a skill: "4 years Golang", "React (1 yr)", "Django ... ~1 year", "5+ years of React".
_SKILL_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*(\+)?\s*(?:yrs?|years?)\b(?!\s*(?:old|of age|of (?:total |overall )?experience))",
                          re.IGNORECASE)


def stated_years(raw: str) -> float | None:
    """'React (1 yr)' -> 1.0   'Python 5+ years' -> 5.0   'Docker' -> None   '16 years old' -> None"""
    match = _STATED_YEARS.search(raw or "")
    return float(match.group(1)) if match else None


def ground_job_skills(skills: list[str], block_text: str) -> tuple[list[str], list[str]]:
    """Keep the skills written in a block of text (any known spelling). Returns (kept, removed). Used by chunking."""
    kept = [s for s in skills if any(contains_phrase(block_text, sp) for sp in spellings(s))]
    return kept, [s for s in skills if s not in kept]


# --------------------------------------------------------------------------- locating entries in the text
def _line_has(normed_line: str, phrase: str) -> bool:
    return bool(phrase) and phrase in normed_line


def _find_entry_line(keys: list[str], normed: list[str], ranges: list[tuple[int, int]], taken: set[int],
                     cursor: int) -> int | None:
    """The first line (in the preferred ranges, after `cursor` first) that contains all keys."""
    keys = [k for k in keys if k]
    if not keys:
        return None
    for lo, hi in ranges + [(0, len(normed))]:
        for begin in (max(lo, cursor), lo):
            for i in range(begin, hi):
                if i in taken:
                    continue
                around = " ".join(normed[i:i + 2])
                if all(k in around for k in keys) and keys[0] in normed[i]:
                    return i
    return None


def _entry_blocks(starts: list[int | None], sections: list[Section], n_lines: int) -> list[tuple[int, int] | None]:
    """Each entry's lines: from its start to the next entry's start, never past the end of its section."""
    found = sorted(s for s in starts if s is not None)
    blocks: list[tuple[int, int] | None] = []
    for start in starts:
        if start is None:
            blocks.append(None)
            continue
        section = section_at(sections, start)
        end = section.end if section else n_lines
        nxt = next((s for s in found if s > start), None)
        if nxt is not None:
            end = min(end, nxt)
        blocks.append((start, max(end, start + 1)))
    return blocks


def _name_keys(name: str) -> list[str]:
    """'Patrishi Sports — Sports & Event Management' -> ['patrishi sports']; '1. HRMS' -> ['hrms']."""
    main = re.split(r"\s[-–—|:]\s|\s\(|\s\[|,", name or "")[0]
    main = re.sub(r"^\s*(\d+[.)]|project name\s*[-:])\s*", "", main, flags=re.IGNORECASE)
    key = _norm(main)
    return [key] if key else []


# --------------------------------------------------------------------------- skills lists
_GENERIC_WORDS = {
    "development", "developing", "analysis", "design", "designing", "coding", "debugging", "testing", "quality",
    "assurance", "documentation", "implementation", "management", "communication", "teamwork", "problem",
    "solving", "building", "delivery", "engineering", "architecture", "strong", "experience", "skills", "and",
    "the", "of", "with", "for", "in", "requirement", "requirements", "software", "application", "applications",
    "mobile", "web", "practices", "working", "knowledge", "understanding", "ability", "ownership",
    "leadership", "collaboration", "integration", "integrations", "custom", "plugin", "plugins", "services",
    "service", "solutions", "system", "systems", "platform", "management", "operations", "optimization",
    "optimisation", "performance", "security", "infrastructure", "support", "tools", "frameworks",
    "build", "deliver", "deployment", "deploy", "develop", "implement", "lead", "work", "architect", "optimize",
    "create", "manage", "maintain", "scaling", "monitoring", "automation", "pipelines", "workflows",
}
_LIST_SPLIT = re.compile(r",|;|\s\|\s|\s/\s|\band\b|&(?=\s)")


def _split_list(text: str) -> list[str]:
    """'WordPress (Custom Plugins), BigCommerce (Stencil CLI, Headless), Shopify' -> 3 items (brackets kept)."""
    items, depth, current = [], 0, ""
    for ch in text:
        depth += ch == "("
        depth -= ch == ")" and depth > 0
        if depth == 0 and ch in ",;":
            items.append(current)
            current = ""
        else:
            current += ch
    items.append(current)
    out = []
    for item in items:
        out.extend(p for p in (_LIST_SPLIT.split(item) if "(" not in item else [item]))
    return [re.sub(r"\s+", " ", i).strip(" .-*") for i in out if i and i.strip(" .-*")]


_CONNECTORS = {"of", "in", "for", "with", "using", "to", "on", "by", "from", "via", "into", "the", "a", "an"}


def _looks_like_skill_name(item: str) -> bool:
    """
    For skills NOT in the catalogue: does the item look like a product name?
      'Airtable', 'Podio' -> yes
      'Mobile application development', 'Integrations of Rest APIs', 'JS in React Native' -> no
      'Bitvavo & Coinbase APIs' -> no (it contains known skills; the dictionary scan already found those)
    """
    if not item or "(" in item or ")" in item:
        return False
    words = item.split()
    if not (1 <= len(words) <= 3) or len(item) > 30:
        return False
    lowered = [w.lower().strip(".,") for w in words]
    if any(w in _GENERIC_WORDS or w in _CONNECTORS for w in lowered):
        return False
    if skills_in_phrase(item):
        return False
    # Product names are written like names: every word capitalised or with a capital/digit inside
    # ("Dymo SDK", "Antigravity IDE", "n8n"); "Rapidly prototype" or "internal AI platforms" are prose.
    return all(w[0].isupper() or any(c.isupper() or c.isdigit() for c in w) for w in words)


def _join_wrapped(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """
    PDFs wrap long lines. In a skills list, a line that continues the previous one (the previous line ends with
    a comma or "&", or has an unclosed bracket, and this line is not a new bullet or "Label:") is joined to it:
      "AI Chatbots, Voice" + "Assistants, OpenAI & Claude APIs."  -> one line
    """
    joined: list[tuple[int, str]] = []
    for i, raw in lines:
        text = raw.strip()
        if not text:
            continue
        new_item = re.match(r"^([-*•]|\d+[.)])\s", text) or re.match(r"^[A-Z][\w &/+.-]{1,40}:", text)
        if joined and not new_item:
            prev_i, prev = joined[-1]
            if prev.rstrip().endswith((",", "&", "/")) or prev.count("(") > prev.count(")") or not prev.rstrip().endswith((".", ":")):
                joined[-1] = (prev_i, f"{prev.rstrip()} {text}")
                continue
        joined.append((i, text))
    return joined


def skills_list_items(lines: list[str]) -> list[tuple[str, int, str]]:
    """
    The items of a skills section, as (canonical name, line index, line text).

      "Ecommerce & CMS: WordPress (Custom Plugins), WooCommerce"      -> WordPress, WooCommerce  (label skipped)
      "- Databases: PostgreSQL, MySQ, MongoDB."                         -> PostgreSQL, MySQL, MongoDB
      "- Backend Engineering: Strong experience with Node.js and ..."   -> (prose: the dictionary scan finds those)
      "- Mobile application development"                                -> nothing (an activity, not a technology)
    """
    out = []
    for i, raw in _join_wrapped(lines):
        line = re.sub(r"^\s*[-*•]\s*", "", raw).strip()
        if not line:
            continue
        label, sep, rest = line.partition(":")
        body = rest if sep and len(label.split()) <= 5 and "http" not in label.lower() else line
        items = _split_list(body)
        if not items or sum(len(i.split()) <= 4 for i in items) / len(items) < 0.6:
            continue                                     # a sentence with commas, not a list
        for item in items:
            for name in normalize_skill(item):
                if is_known(name) or _looks_like_skill_name(name):
                    out.append((name, i, raw.strip()))
    return out


# --------------------------------------------------------------------------- education
_YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")


def ground_education(entries: list[dict], resume_text: str) -> list[dict]:
    """
    Keep an education entry's year only if the RESUME shows it near that entry (Step 12 finding: the 3B model
    wrote chatter like "goes here" as years). The degree's or institution's line and the 2 lines after it are
    searched (PDFs wrap long institution names). For "2010-2013" the finishing year is kept.
    Idempotent, so it is also applied when an old profile is read.
    """
    lines = [line.strip() for line in resume_text.splitlines()]
    normed = [_norm(line) for line in lines]
    grounded = []
    for entry in entries:
        entry = dict(entry)
        keys = [k for k in (_norm(entry.get("degree") or "")[:30], _norm(entry.get("institution") or "")[:25]) if k]
        nearby = ""
        for key in keys:
            idx = next((i for i, n in enumerate(normed) if key and key in n), None)
            if idx is not None:
                nearby = " ".join(lines[idx:idx + 3])
                break
        found = _YEAR.findall(nearby)
        claimed = _YEAR.findall(str(entry.get("year") or ""))
        if claimed and claimed[-1] in found:
            entry["year"] = claimed[-1]
        else:
            entry["year"] = found[-1] if found else None
        grounded.append(entry)
    return grounded


# --------------------------------------------------------------------------- durations
_DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(years?|yrs?|months?|mos?)\b", re.IGNORECASE)


def duration_months(text: str | None) -> int | None:
    """'6 Months' -> 6 · '1 year 2 months' -> 14 · None -> None"""
    total, found = 0.0, False
    for number, unit in _DURATION.findall(text or ""):
        found = True
        total += float(number) * (12 if unit.lower().startswith(("y", "yr")) else 1)
    return round(total) if found else None


_EXPOSURE = re.compile(r"\b(team (?:who|that|which)|exposure to|assisted (?:the )?team)\b", re.IGNORECASE)
_URL = re.compile(r"https?://\S+")


# --------------------------------------------------------------------------- main function
def build_profile(llm: ResumeExtraction, resume_text: str, today: date | None = None) -> Profile:
    today = today or date.today()
    warnings: list[str] = []
    rejected: list[dict] = []
    lines, sections = split_sections(resume_text)
    normed = [_norm(line) for line in lines]
    ranges_of = lambda *kinds: [(s.heading_line or s.start, s.end) for s in sections if s.kind in kinds]  # noqa: E731

    # ---- 1. Jobs: dates, and their lines in the text
    jobs: list[ProfileJob] = []
    spans: list[tuple[int, int] | None] = []
    for job in llm.experience:
        start, end, current = parse_range(job.start, job.end)
        span = interval(start, end, current, today)
        if job.start and span is None:
            warnings.append(f"Could not read the dates of job '{job.title}' ({job.start} - {job.end}).")
        jobs.append(ProfileJob(
            title=job.title, company=job.company,
            start_date=start.as_date() if start else None,
            end_date=end.as_date() if end else None,
            is_current=current, months=(span[1] - span[0] + 1) if span else None,
            description=job.description, skills=[],
        ))
        spans.append(span)

    taken: set[int] = set()
    job_starts: list[int | None] = []
    cursor = 0
    for job in llm.experience:
        company = _norm(job.company or "")[:40]
        title = _norm(job.title or "")[:40]
        pos = _find_entry_line([company, title] if company else [title], normed, ranges_of(EXPERIENCE), taken, cursor)
        if pos is None and company:
            pos = _find_entry_line([company], normed, ranges_of(EXPERIENCE), taken, cursor)
        if pos is None and title:
            pos = _find_entry_line([title], normed, ranges_of(EXPERIENCE), taken, cursor)
        if pos is None:
            warnings.append(f"Could not find job '{job.title}' at '{job.company}' in the resume text.")
        else:
            taken.add(pos)
            cursor = pos + 1
        job_starts.append(pos)
    job_blocks = _entry_blocks(job_starts, sections, len(lines))

    # ---- 2. Projects: their lines, technologies checked against those lines
    project_starts: list[int | None] = []
    cursor = 0
    for project in llm.projects:
        pos = _find_entry_line(_name_keys(project.name), normed, ranges_of(PROJECTS, EXPERIENCE), taken, cursor)
        if pos is None:
            warnings.append(f"Could not find project '{project.name}' in the resume text; it was left out.")
        else:
            taken.add(pos)
            cursor = pos + 1
        project_starts.append(pos)
    project_blocks = _entry_blocks(project_starts, sections, len(lines))

    def job_containing(line: int) -> int | None:
        for j, block in enumerate(job_blocks):
            if block and block[0] <= line < block[1]:
                return j
        return None

    projects: list[ProfileProject] = []
    kept_project_blocks: list[tuple[int, int]] = []
    for project, block in zip(llm.projects, project_blocks):
        if block is None:
            continue
        block_text = "\n".join(lines[block[0]:block[1]])
        block_norm = _norm(block_text)
        techs: list[str] = []
        for raw in project.technologies:
            if not appears_in(raw, block_norm, 0.9):
                rejected.append({"name": raw, "project": project.name,
                                 "reason": "listed for this project by the model, but not written in its text"})
                continue
            for name in normalize_skill(raw):
                if (is_known(name) or _looks_like_skill_name(name)) and name not in techs:
                    techs.append(name)
        for name, _, _ in find_skills(block_text):
            # Ways of working ("Project Manager & Tech Lead" -> Project management) are not technologies.
            if name not in techs and category_of(name) != "practice":
                techs.append(name)
        job_index = job_containing(block[0])
        basis = "inside job" if job_index is not None else None
        if job_index is None and len(jobs) == 1:
            job_index, basis = 0, "only employer"
        link = next(iter(_URL.findall(block_text)), None)
        projects.append(ProfileProject(
            name=re.sub(r"^\s*\d+[.)]\s*", "", project.name).strip(), role=project.role,
            duration_text=project.duration if project.duration and appears_in(project.duration, block_norm) else None,
            duration_months=duration_months(project.duration) if project.duration and appears_in(project.duration, block_norm) else None,
            technologies=techs, description=project.description, link=link and link.rstrip(".,)"),
            job_index=job_index, job_basis=basis,
        ))
        kept_project_blocks.append(block)

    def project_containing(line: int) -> int | None:
        for p, block in enumerate(kept_project_blocks):
            if block[0] <= line < block[1]:
                return p
        return None

    # ---- 3. Skill mentions: where is each skill written?
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line) + 1)

    def line_of(offset: int) -> int:
        lo, hi = 0, len(lines) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    @dataclass
    class Usage:
        jobs: set = field(default_factory=set)
        projects: set = field(default_factory=set)
        listed: bool = False
        claimed: bool = False
        exposure_only_line: str | None = None
        evidence: dict = field(default_factory=dict)     # source -> line text
        api_only: bool = True                            # only ever written as "X API(s)": integrated, not built with

    usage: dict[str, Usage] = {}

    def record(name: str, line_index: int, from_list: bool = False, api: bool = False) -> None:
        u = usage.setdefault(name, Usage())
        u.api_only = u.api_only and api
        text = lines[line_index].strip()
        if _EXPOSURE.search(text):
            u.exposure_only_line = u.exposure_only_line or text
            return
        section = section_at(sections, line_index)
        project = project_containing(line_index)
        job = job_containing(line_index)
        if project is not None:
            u.projects.add(project)
            u.evidence.setdefault("project", text)
        elif job is not None and (section is None or section.kind == EXPERIENCE):
            u.jobs.add(job)
            u.evidence.setdefault("job", text)
        elif len(jobs) == 1 and section and section.kind == RESPONSIBILITIES:
            # A "Key Responsibilities" section of someone with ONE employer describes the work done there.
            u.jobs.add(0)
            u.evidence.setdefault("job", text)
        elif from_list or (section and section.kind == SKILLS):
            u.listed = True
            u.evidence.setdefault("skills list", text)
        else:
            u.claimed = True
            u.evidence.setdefault("mentioned", text)

    # Durations written next to a skill. Without "+" ("4 years Golang", "~1 year") they cap the skill's years;
    # with "+" ("5+ years of React") they are a minimum, used only when no dated job shows the skill.
    stated_cap: dict[str, float] = {}
    stated_min: dict[str, float] = {}
    mentions = find_skills(resume_text)
    by_line: dict[int, list[tuple[str, int, int]]] = {}
    for name, start, end in mentions:
        by_line.setdefault(line_of(start), []).append((name, start, end))
    for i, found in by_line.items():
        line = lines[i]
        if not _SKILL_YEARS.search(line):
            continue
        names = list(dict.fromkeys(n for n, _, _ in found))
        if len(names) == 1:
            clauses = [(line, names)]
        else:                                   # several skills: only the one in the same clause
            base = line_starts[i]
            clauses = []
            for part in re.finditer(r"[^,;|]+", line):
                inside = [n for n, s0, _ in found if part.start() <= s0 - base < part.end()]
                clauses.append((part.group(0), list(dict.fromkeys(inside))))
        for clause, inside in clauses:
            if len(inside) != 1:
                continue
            m = _SKILL_YEARS.search(clause)
            if not m:
                continue
            value = float(m.group(1))
            target = stated_min if m.group(2) else stated_cap
            target[inside[0]] = min(target.get(inside[0], value), value)

    for name, start, end in mentions:
        # "integrates multiple WordPress APIs": calling a system's API is not building with it (no PHP implied)
        api = category_of(name) != "integration" and bool(re.match(r"\s+APIs?\b", resume_text[end:end + 6]))
        record(name, line_of(start), api=api)
    for section in sections:
        if section.kind == SKILLS:
            items = skills_list_items([(i, lines[i]) for i in range(section.start, section.end)])
            for name, i, _ in items:
                if not is_known(name):                  # known names were found by the scan already
                    record(name, i, from_list=True)
    for p, project in enumerate(projects):              # unknown project technologies ("Dymo Hardware SDK")
        for name in project.technologies:
            if name not in usage:
                line = next((lines[i].strip() for i in range(*kept_project_blocks[p]) if name.lower() in lines[i].lower()),
                            None)
                usage[name] = Usage(projects={p}, evidence={"project": line or project.name}, api_only=False)

    # Using a framework in a job or project means using its language there too (Laravel -> PHP).
    for name in list(usage):
        if usage[name].api_only:
            continue
        for implied in with_implied_use([name])[1:]:
            u, source = usage.setdefault(implied, Usage()), usage[name]
            u.jobs |= source.jobs
            u.projects |= source.projects
            if source.jobs or source.projects:
                # The evidence is the real line where the framework is written (never invented text).
                line = source.evidence.get("job") or source.evidence.get("project")
                if line:
                    u.evidence.setdefault("implied", line)
    for j, job in enumerate(jobs):
        job.skills = [n for n, u in usage.items() if j in u.jobs]

    # ---- 4. Skills with years
    skills: list[ProfileSkill] = []
    for name, u in usage.items():
        if not (u.jobs or u.projects or u.listed or u.claimed):
            if u.exposure_only_line:
                rejected.append({"name": name, "evidence": u.exposure_only_line,
                                 "reason": "only written as someone else's work (e.g. 'worked with a team who ...')"})
            continue
        since = TECH_SINCE.get(name)
        job_spans = []
        for j in sorted(u.jobs):
            if spans[j] is None:
                continue
            first, last = spans[j]
            if since:
                first = max(first, since * 12)              # not before the technology existed
            if first <= last:
                job_spans.append((first, last))
        years = months_to_years(total_months(job_spans)) if job_spans else None
        if name in stated_cap:                           # "~1 year" next to the skill: never more than that
            years = min(years, stated_cap[name]) if years is not None else stated_cap[name]
        elif years is None and name in stated_min:       # "5+ years of React" and no dated job shows it
            years = stated_min[name]
        last_used = None
        for j in u.jobs:
            if jobs[j].is_current:
                last_used = today.year
            elif jobs[j].end_date:
                last_used = max(last_used or 0, jobs[j].end_date.year)
        for p in u.projects:
            j = projects[p].job_index
            if j is not None and projects[p].job_basis == "inside job":
                end_year = today.year if jobs[j].is_current else (jobs[j].end_date.year if jobs[j].end_date else None)
                last_used = max(last_used or 0, end_year or 0) or last_used
        source = ("job" if u.jobs else "project" if u.projects else "skills list" if u.listed else "mentioned")
        evidence = u.evidence.get(source) or u.evidence.get("implied") or next(iter(u.evidence.values()), None)
        skills.append(ProfileSkill(
            name=name, category=category_of(name), years=years, last_used_year=last_used,
            evidence=(evidence or "")[:300] or None, uses=len(u.jobs) + len(u.projects), source=source,
        ))
    rank = {"job": 0, "project": 1, "skills list": 2, "mentioned": 3}
    skills.sort(key=lambda s: (-(s.years or 0), -s.uses, rank[s.source], s.name.lower()))

    # ---- 5. Total experience: dated jobs, else what the resume states
    valid = [s for s in spans if s]
    computed = months_to_years(total_months(valid)) if valid else None
    intro = "\n".join(s.text(lines) for s in sections if s.kind in (HEADER, SUMMARY)) or "\n".join(lines[:15])
    claimed_years = stated_years(intro)
    total, basis = computed, ("dated jobs" if computed is not None else None)
    if claimed_years is not None:
        if computed is None:
            total, basis = claimed_years, "stated in resume"
        elif claimed_years - computed > 1.5:
            warnings.append(f"The resume states {claimed_years:g}+ years, but its dated jobs cover {computed} years; "
                            "the stated value is used.")
            total, basis = claimed_years, "stated in resume"
        elif computed - claimed_years > 2:
            warnings.append(f"The dated jobs cover {computed} years, more than the {claimed_years:g} years stated.")

    if not llm.experience and not projects:
        warnings.append("No jobs or projects were found.")

    education_entries = [e.model_dump() for e in llm.education if e.degree or e.institution]
    return Profile(
        headline=llm.headline, summary=llm.summary, total_experience_years=total,
        jobs=jobs, skills=skills,
        education=ground_education(education_entries, resume_text),
        certifications=[c for c in llm.certifications if c.strip()],
        projects=projects, experience_basis=basis, stated_years=claimed_years,
        rejected_skills=rejected, warnings=warnings,
    )


# Public names for chunking (rag/chunking.py), which locates jobs and projects the same way.
find_entry_line, entry_blocks, name_keys = _find_entry_line, _entry_blocks, _name_keys

__all__ = [
    "Profile", "ProfileJob", "ProfileProject", "ProfileSkill", "appears_in", "build_profile", "contains_phrase",
    "duration_months", "ground_education", "ground_job_skills", "normalize_for_match", "skills_list_items",
    "stated_years", "entry_blocks", "find_entry_line", "name_keys",
]
