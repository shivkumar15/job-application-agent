"""Truthful, template-based application material for a captured listing."""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.matching import CandidateProfile, _candidate_skills, _job_skills


class PrepareApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dedupe_key: str = Field(min_length=16, max_length=128)
    candidate_profile: CandidateProfile


def _section_text(section: Any) -> str:
    if isinstance(section, str):
        return section.strip()
    if isinstance(section, dict):
        value = section.get("section_text", "")
        return value.strip() if isinstance(value, str) else ""
    return ""


def _evidence_skills(profile: CandidateProfile, matched: set[str]) -> list[str]:
    evidence = " ".join(
        [
            _section_text(profile.experience),
            _section_text(profile.projects),
            profile.summary or "",
        ]
    ).casefold()
    return sorted(
        skill
        for skill in matched
        if re.search(
            r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])",
            evidence,
        )
    )


def _display(value: str) -> str:
    labels = {
        "react.js": "React.js",
        "node.js": "Node.js",
        "javascript": "JavaScript",
        "mongodb": "MongoDB",
        "tailwind css": "Tailwind CSS",
        "rest apis": "REST APIs",
        "numpy": "NumPy",
        "pandas": "Pandas",
        "jwt": "JWT",
        "sql": "SQL",
        "html5": "HTML5",
        "css3": "CSS3",
    }
    return labels.get(value, value.title())


def prepare_application_material(profile: CandidateProfile, job: dict) -> dict:
    """Create drafts using only captured job fields and reviewed resume data."""
    candidate_skills = _candidate_skills(profile)
    job_skills = _job_skills(job)
    matched = candidate_skills & job_skills
    missing = job_skills - candidate_skills
    evidence = _evidence_skills(profile, matched)

    title = str(job.get("title", "the internship")).strip()
    company = str(job.get("company", "the company")).strip()
    matched_labels = [_display(skill) for skill in sorted(matched)]
    evidence_labels = [_display(skill) for skill in evidence]
    missing_labels = [_display(skill) for skill in sorted(missing)]

    if matched_labels:
        skills_sentence = (
            "My reviewed resume lists relevant skills including "
            + ", ".join(matched_labels)
            + "."
        )
    else:
        skills_sentence = (
            "I would welcome the opportunity to discuss how my background "
            "aligns with the requirements of this role."
        )

    if evidence_labels:
        evidence_sentence = (
            "My experience and project sections specifically mention "
            + ", ".join(evidence_labels)
            + "."
        )
    else:
        evidence_sentence = (
            "Please refer to my resume for the details of my education, "
            "internship experience, and projects."
        )

    cover_letter = (
        "Dear Hiring Team,\n\n"
        f"I am writing to apply for the {title} opportunity at {company}. "
        f"{skills_sentence} {evidence_sentence}\n\n"
        "I am interested in learning more about the role and discussing how "
        "the work documented in my resume may contribute to your team. "
        "I would be glad to provide any additional information.\n\n"
        "Thank you for your time and consideration.\n\n"
        "Regards,\n[Your Name]"
    )

    email_subject = f"Application for {title} - [Your Name]"
    email_body = (
        "Dear Hiring Team,\n\n"
        f"I would like to apply for the {title} position at {company}. "
        f"{skills_sentence}\n\n"
        "I have attached my resume for your review. I would appreciate the "
        "opportunity to discuss my application.\n\n"
        "Regards,\n[Your Name]"
    )

    warnings = [
        "These are template-based drafts, not AI-generated or independently verified claims.",
        "Review every statement, replace [Your Name], and attach your resume before sending.",
        "Do not add missing job skills to your resume unless you genuinely have that skill and can support it.",
    ]
    if profile.parsing.get("requires_review", False):
        warnings.append("The extracted resume profile is marked for review.")

    return {
        "job": {
            "title": title,
            "company": company,
            "apply_url": job.get("apply_url"),
        },
        "email": {"subject": email_subject, "body": email_body},
        "cover_letter": cover_letter,
        "resume_guidance": {
            "skills_to_highlight": matched_labels,
            "skills_not_found_in_resume": missing_labels,
            "evidence_skills": evidence_labels,
        },
        "warnings": warnings,
        "submission_status": "draft_only",
        "note": "Nothing has been sent or submitted. User approval is required for any future submission workflow.",
    }
