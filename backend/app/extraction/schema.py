"""
The exact JSON shape the LLM must return.

Ollama receives ResumeExtraction.model_json_schema() and is FORCED to produce JSON that
fits it ("structured outputs"). Then Pydantic validates the reply against the same classes.

Design rule: the LLM only COPIES and LABELS what is written. Anything that needs
calculation or consistency (years of experience, skill spelling, date maths) is done
afterwards in plain Python (postprocess.py), because code is exact and LLMs are not.
"""
from pydantic import BaseModel


class SkillMention(BaseModel):
    name: str              # as written in the resume, e.g. "k8s (EKS)"
    evidence: str          # short exact quote proving it, e.g. "Operate 14 EKS clusters (k8s 1.2x)"


class Job(BaseModel):
    title: str | None
    company: str | None
    start: str | None      # as written: "Jun 2021", "03/2022", "2018"
    end: str | None        # as written, or "Present"
    description: str | None
    skills_used: list[str]


class Education(BaseModel):
    degree: str | None
    institution: str | None
    year: str | None


class ResumeExtraction(BaseModel):
    headline: str | None
    summary: str | None
    experience: list[Job]
    skills: list[SkillMention]
    education: list[Education]
    certifications: list[str]
