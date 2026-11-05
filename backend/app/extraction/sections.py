"""
Splitting a resume into its sections: summary, skills, experience, projects, education ...

Why in code and not left to the LLM: every later step needs to know WHERE a piece of text is. A skill in a
"Technical Skills" list is a claim; the same skill inside a project or job is evidence of use. Chunks for
search must not glue a project onto the job above it (finding in doc 07: Ajay's 6 projects were labelled as
his 2013-2018 job because "KEY PROJECTS" was not a known heading).

Real resumes (doc 18) name the same section in many ways: "Profile Summary", "Technical Expertise",
"TECHNICAL SHOWCASE", "Project delivered", "Projects Delivered", "Employment History" ... A line is a heading
when it LOOKS like one (short, no sentence punctuation, not a bullet) AND either names a known section or is
written in CAPITALS.
"""
import re
from dataclasses import dataclass

# Section kinds. "header" is the text above the first heading (name, title, contact line).
HEADER, SUMMARY, SKILLS, EXPERIENCE, PROJECTS = "header", "summary", "skills", "experience", "projects"
RESPONSIBILITIES, ACHIEVEMENTS, EDUCATION, CERTIFICATIONS, OTHER = (
    "responsibilities", "achievements", "education", "certifications", "other",
)

# Heading text (lowercase, "&" -> "and", without a trailing ":") -> section kind.
HEADINGS: dict[str, str] = {}
for kind, names in {
    SUMMARY: ["summary", "profile", "profile summary", "professional summary", "career summary", "about",
              "about me", "objective", "career objective", "overview", "professional profile", "executive summary",
              "personal profile", "introduction"],
    SKILLS: ["skills", "technical skills", "key skills", "core skills", "skill set", "skillset", "skills summary",
             "technical expertise", "expertise", "areas of expertise", "technical showcase", "technologies",
             "tech stack", "technology stack", "technical stack", "core competencies", "competencies",
             "technical proficiency", "technical proficiencies", "tools and technologies", "technologies and tools",
             "it skills", "software skills", "programming skills", "technical summary", "key technologies"],
    EXPERIENCE: ["experience", "work experience", "professional experience", "employment history", "employment",
                 "work history", "career history", "professional history", "relevant experience",
                 "experience summary", "organisational experience", "organizational experience", "career"],
    PROJECTS: ["projects", "project", "key projects", "project delivered", "projects delivered", "project experience",
               "project details", "personal projects", "notable projects", "selected projects", "major projects",
               "academic projects", "project portfolio", "portfolio", "projects handled", "projects worked on"],
    RESPONSIBILITIES: ["responsibilities", "key responsibilities", "roles and responsibilities",
                       "role and responsibilities", "duties"],
    ACHIEVEMENTS: ["achievements", "key achievements", "awards", "accomplishments", "honors", "honours",
                   "awards and achievements", "recognition"],
    EDUCATION: ["education", "academic", "academics", "qualification", "qualifications", "educational qualification",
                "educational qualifications", "academic qualifications", "academic background", "education details"],
    CERTIFICATIONS: ["certifications", "certification", "certificates", "licenses", "licences",
                     "licenses and certifications", "certifications and trainings", "trainings", "training"],
    OTHER: ["languages", "interests", "hobbies", "references", "personal details", "personal information",
            "contact", "contact details", "declaration", "extra-curricular activities", "volunteering",
            "publications", "strengths"],
}.items():
    for name in names:
        HEADINGS[name] = kind

_BULLET_START = re.compile(r"^\s*([-*•●▪]|\d+[.)])\s")


@dataclass
class Section:
    kind: str           # one of the kinds above
    heading: str | None  # the heading line as written (None for the header block)
    start: int          # first line index of the section's BODY (after the heading)
    end: int            # line index after the section's last line
    heading_line: int | None

    def text(self, lines: list[str]) -> str:
        return "\n".join(lines[self.start:self.end]).strip()


def _heading_key(line: str) -> str:
    key = re.sub(r"\s+", " ", line.strip().rstrip(":").replace("&", " and ")).strip().lower()
    return re.sub(r"\s+", " ", key)


def heading_kind(line: str) -> str | None:
    """The section kind if this line is a heading, else None.

    "TECHNICAL SKILLS" -> skills · "Projects Delivered" -> projects · "Key Responsibilities:" -> responsibilities
    "SmartGas" -> None (a project name, Title Case but not a known heading) · "- Skills used" -> None (a bullet)
    """
    text = line.strip()
    if not (2 <= len(text) <= 50) or _BULLET_START.match(text):
        return None
    if text.endswith((".", ",", ";")) or ":" in text.rstrip(":"):
        return None                       # sentences and "Label: value" lines are content
    if len(text.split()) > 6:
        return None
    kind = HEADINGS.get(_heading_key(text))
    if kind:
        return kind
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.9:
        return OTHER                      # an unknown heading in CAPITALS ("PERSONAL DOSSIER")
    return None


def split_sections(text: str) -> tuple[list[str], list[Section]]:
    """The resume's lines, and its sections in order. Text above the first heading is the 'header' section."""
    lines = text.split("\n")
    marks = [(i, heading_kind(line)) for i, line in enumerate(lines)]
    marks = [(i, kind) for i, kind in marks if kind]

    # A capitalised name at the very top ("AJAY CHANDANI", "RAVI") is not a section heading.
    first_content = next((i for i, line in enumerate(lines) if line.strip()), 0)
    marks = [(i, kind) for i, kind in marks if not (i == first_content and kind == OTHER)]

    # Inside a job or a project, "Key Responsibilities:" is a sub-label of that entry, not a new section
    # (R4 and R9 in doc 18 have one under every project).
    kept: list[tuple[int, str]] = []
    for i, kind in marks:
        if kind == RESPONSIBILITIES and kept and kept[-1][1] in (EXPERIENCE, PROJECTS):
            continue
        kept.append((i, kind))
    marks = kept

    sections: list[Section] = []
    first = marks[0][0] if marks else len(lines)
    if any(line.strip() for line in lines[:first]):
        sections.append(Section(HEADER, None, 0, first, None))
    for n, (i, kind) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        sections.append(Section(kind, lines[i].strip(), i + 1, end, i))
    return lines, sections


def section_at(sections: list[Section], line_index: int) -> Section | None:
    """The section a line belongs to (headings belong to their own section)."""
    for s in sections:
        start = s.heading_line if s.heading_line is not None else s.start
        if start <= line_index < s.end:
            return s
    return None
