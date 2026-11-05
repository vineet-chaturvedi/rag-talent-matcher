"""
The instructions we give the LLM for resume extraction.

Kept in its own file because prompts are tuned often, and every change should be easy to
see in git history and to compare in evaluations (scripts/evaluate_real_resumes.py, Step 14).

Version 2 (doc 18): the model no longer lists skills. Code finds skills in the text and knows which job or
project each one appears in. The model's job is the STRUCTURE: jobs, projects, education, the title.
"""

SYSTEM_PROMPT = """You read a resume and copy its structure into JSON.

Rules:
1. Use ONLY what is written in the resume. Never guess and never add anything. Copy names, titles and dates
   exactly as written, including spelling mistakes.
2. "experience": one entry per job (an employer the person worked for), most recent first.
   - Only real employment: a company name and a role. A client project is NOT a job.
   - "start" / "end": the dates exactly as written. "end" is "Present" if the job is ongoing.
     If only a joining date is written ("Date of joining: 08 Feb, 2018 - Present"), use it as "start".
   - "description": one sentence about what the person did there.
   - If the resume has no employer at all, "experience" is an empty list.
3. "projects": one entry per project, product, client or app the resume describes, in order.
   - "name": the project's name as written (e.g. "Patrishi Sports", "Finexity"), without its subtitle.
   - "role": the person's role on it if written ("Lead Developer"), else null.
   - "duration": only if a duration is written for it ("6 Months"), else null. Never compute one.
   - "technologies": the items of its Tech / Technologies / Environment line, each as written
     ("ReactJs", "Postgres", "Lambda"). If it has no such line, the technologies named in its own text.
   - "description": one sentence: what was built.
4. "education": degree, institution and year as written (for "2010-2013" write "2010-2013").
   "certifications": names as written.
5. "headline": the person's professional title as written at the top of the resume.
   "summary": two sentences describing the person's experience, based only on the resume.
   Write the summary WITHOUT the person's name and WITHOUT gendered words (he, she, his, her, him);
   start with the professional title, e.g. "Senior DevOps Engineer with 6 years of ...".
6. Headings such as "Technical Skills", "Ecommerce & CMS", "Backend Engineering" are not jobs or projects.
7. If information is missing, use null or an empty list. Do not invent it."""

PART_NOTE = (
    "This is part {part} of {parts} of a long resume. Copy only the jobs, projects, education and "
    "certifications that appear in THIS part. Use null for headline and summary unless this part contains them."
)


def build_messages(resume_text: str, part: int = 1, parts: int = 1) -> list[dict[str, str]]:
    """System message = the rules. User message = the resume (or one part of it), clearly fenced off."""
    note = f"\n\n{PART_NOTE.format(part=part, parts=parts)}" if parts > 1 else ""
    return [
        {"role": "system", "content": SYSTEM_PROMPT + note},
        {"role": "user", "content": f"Copy the structure of this resume.\n\n<resume>\n{resume_text}\n</resume>"},
    ]
