"""
The instructions we give the LLM for resume extraction.

Kept in its own file because prompts are tuned often, and every change should be easy to
see in git history and to compare in evaluations (Step 14).
"""

SYSTEM_PROMPT = """You extract facts from a resume into JSON.

Rules:
1. Use ONLY information written in the resume. Never guess, never add anything that is not there.
2. Copy job titles, company names and dates exactly as they are written.
3. "skills": every technical skill, programming language, framework, tool, database, cloud platform,
   certification topic or method mentioned ANYWHERE (skills section, job descriptions, summary).
   - "name": the skill as written.
   - "evidence": a short exact quote from the resume (at most 12 words) that shows the skill.
4. "experience": one entry per job or role, most recent first.
   - "start" / "end": the dates exactly as written. Use "Present" for "end" if the job is ongoing.
   - "description": one sentence summarising what the person did in that role.
   - "skills_used": skills clearly used in that role. Include the programming language when a framework
     used in the role implies it (Django, FastAPI, Flask -> Python; Spring Boot -> Java).
5. "education": degree, institution and year as written. "certifications": names as written.
6. "headline": the person's current professional title.
   "summary": two sentences describing the person's experience, based only on the resume.
7. If information is missing, use null or an empty list. Do not invent it."""


def build_messages(resume_text: str) -> list[dict[str, str]]:
    """System message = the rules. User message = the resume, clearly fenced off."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract the facts from this resume.\n\n<resume>\n{resume_text}\n</resume>"},
    ]
