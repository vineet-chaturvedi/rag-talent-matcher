"""
The exact JSON shape the LLM must return.

Ollama receives ResumeExtraction.model_json_schema() and is FORCED to produce JSON that
fits it ("structured outputs"). Then Pydantic validates the reply against the same classes.

Design rule: the LLM only COPIES and LABELS the STRUCTURE of the resume: which jobs, which projects, which
degrees. Everything that needs exact matching or arithmetic is done afterwards in plain Python
(postprocess.py): finding skills (a dictionary scan of the whole text), years, dates, where each skill was used.

Version 2 (doc 18, real resumes): projects added, because in 8 of 9 real resumes projects are the main
content; the model's "skills" lists removed, because the model turned headings ("Ecommerce & CMS") into skills
and dropped listed ones (Python, Django). Without them the answer is also much shorter, so long resumes fit.
"""
from pydantic import BaseModel, Field


class Job(BaseModel):
    title: str | None
    company: str | None
    start: str | None      # as written: "Jun 2021", "03/2022", "2018", "08 Feb, 2018"
    end: str | None        # as written, or "Present"
    description: str | None


class Project(BaseModel):
    name: str                                   # as written: "Patrishi Sports", "Finexity"
    role: str | None                            # "Lead Developer", "Mobile App Developer"
    duration: str | None                        # only if written next to the project: "6 Months"
    technologies: list[str] = Field(default_factory=list)   # as written in the project's Tech/Environment line
    description: str | None                     # one sentence: what was built


class Education(BaseModel):
    degree: str | None
    institution: str | None
    year: str | None


class ResumeExtraction(BaseModel):
    headline: str | None
    summary: str | None
    experience: list[Job]
    projects: list[Project] = Field(default_factory=list)
    education: list[Education]
    certifications: list[str]
