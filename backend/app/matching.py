"""Transparent, rule-based resume-to-job matching.

This module intentionally avoids external AI calls. Scores are explainable and
should be treated as decision support, not as a guarantee of hiring outcomes.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.resume_parser import SKILL_TERMS


SKILL_ALIASES = {
    "react": "react.js",
    "reactjs": "react.js",
    "node": "node.js",
    "nodejs": "node.js",
    "expressjs": "express",
    "mongo": "mongodb",
    "js": "javascript",
    "tailwind": "tailwind css",
    "tailwindcss": "tailwind css",
    "express.js": "express",
    "restapi": "rest apis",
    "restapis": "rest apis",
    "github": "github",
}

SKILL_DISPLAY = {
    "react.js": "React.js",
    "node.js": "Node.js",
    "javascript": "JavaScript",
    "mongodb": "MongoDB",
    "html5": "HTML5",
    "css3": "CSS3",
    "tailwind css": "Tailwind CSS",
    "rest apis": "REST APIs",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "matplotlib": "Matplotlib",
    "sql": "SQL",
    "c++": "C++",
    "c": "C",
    "jwt": "JWT",
    "api": "API",
}

# Single-letter C is deliberately excluded from free-text detection because it
# appears in ordinary words and can create misleading matches.
DETECTABLE_SKILLS = [skill for skill in SKILL_TERMS if skill.casefold() != "c"]


class CandidateProfile(BaseModel):
    """Subset of the Phase 1 parser response needed for matching."""

    model_config = ConfigDict(extra="ignore")

    skills: list[str] = Field(default_factory=list)
    experience: dict[str, Any] = Field(default_factory=dict)
    projects: dict[str, Any] = Field(default_factory=dict)
    education: dict[str, Any] = Field(default_factory=dict)
    achievements: dict[str, Any] = Field(default_factory=dict)
    parsing: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None


class MatchingPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_roles: list[str] = Field(
        default_factory=lambda: [
            "MERN Stack Developer Intern",
            "Full Stack Developer Intern",
        ],
        min_length=1,
        max_length=20,
    )
    paid_only: bool = True
    work_modes: list[Literal["remote", "onsite", "hybrid"]] = Field(
        default_factory=lambda: ["remote", "onsite"],
        max_length=3,
    )
    minimum_stipend_amount: float = Field(default=0, ge=0, le=1000000)


class MatchJobsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_profile: CandidateProfile
    preferences: MatchingPreferences = Field(default_factory=MatchingPreferences)


def _normalize_skill(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9+#.]", "", value.casefold())
    return SKILL_ALIASES.get(normalized, normalized)


def _display_skill(value: str) -> str:
    return SKILL_DISPLAY.get(value, value.title())


def _section_text(section: Any) -> str:
    if isinstance(section, str):
        return section
    if isinstance(section, dict):
        value = section.get("section_text", "")
        return value if isinstance(value, str) else ""
    return ""


def _candidate_skills(profile: CandidateProfile) -> set[str]:
    return {
        _normalize_skill(skill)
        for skill in profile.skills
        if isinstance(skill, str) and skill.strip()
    }


def _job_skills(job: dict[str, Any]) -> set[str]:
    found = {
        _normalize_skill(skill)
        for skill in job.get("skills", [])
        if isinstance(skill, str) and skill.strip()
    }
    searchable_text = f"{job.get('title', '')} {job.get('description', '')}"
    for skill in DETECTABLE_SKILLS:
        if re.search(
            r"(?<![a-z0-9])" + re.escape(skill.casefold()) + r"(?![a-z0-9])",
            searchable_text,
            re.IGNORECASE,
        ):
            found.add(_normalize_skill(skill))
    return found


def _role_family(value: str) -> str | None:
    text = value.casefold().replace("-", " ")
    if "mern" in text:
        return "mern"
    if re.search(r"full\s*stack", text):
        return "full_stack"
    if "front end" in text or "frontend" in text:
        return "frontend"
    if "back end" in text or "backend" in text:
        return "backend"
    if "machine learning" in text or re.search(r"\bml\b", text):
        return "machine_learning"
    return None


def _role_similarity(job_title: str, target_roles: list[str]) -> float:
    job_family = _role_family(job_title)
    best = 0.0
    for target in target_roles:
        target_family = _role_family(target)
        if job_family and target_family and job_family == target_family:
            return 1.0

        def tokens(value: str) -> set[str]:
            words = set(re.findall(r"[a-z]+", value.casefold()))
            words.discard("intern")
            words.discard("internship")
            words = {"developer" if word == "development" else word for word in words}
            return words

        job_tokens = tokens(job_title)
        target_tokens = tokens(target)
        if job_tokens and target_tokens:
            similarity = len(job_tokens & target_tokens) / len(job_tokens | target_tokens)
            best = max(best, similarity)
    return best


def _match_one(
    profile: CandidateProfile,
    preferences: MatchingPreferences,
    job: dict[str, Any],
) -> dict[str, Any]:
    candidate_skills = _candidate_skills(profile)
    job_skills = _job_skills(job)
    matched = candidate_skills & job_skills
    missing = job_skills - candidate_skills

    evidence_text = " ".join(
        [
            _section_text(profile.experience),
            _section_text(profile.projects),
            profile.summary or "",
        ]
    )
    evidence_skills = {
        skill
        for skill in matched
        if re.search(
            r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])",
            evidence_text,
            re.IGNORECASE,
        )
    }

    skill_points = 50 * len(matched) / len(job_skills) if job_skills else 0.0
    role_similarity = _role_similarity(
        str(job.get("title", "")), preferences.target_roles
    )
    role_points = 25 * role_similarity
    experience_points = (
        15 * len(evidence_skills) / len(job_skills) if job_skills else 0.0
    )

    stipend_status = job.get("stipend_status", "unknown")
    work_mode = job.get("work_mode", "unknown")
    stipend_amount = job.get("stipend_amount")
    paid_points = 5.0 if stipend_status == "paid" else 0.0
    if preferences.work_modes:
        work_mode_points = 5.0 if work_mode in preferences.work_modes else 0.0
    else:
        work_mode_points = 5.0
    preference_points = paid_points + work_mode_points

    score = round(
        min(100.0, skill_points + role_points + experience_points + preference_points)
    )

    reasons = []
    if matched:
        reasons.append(
            f"{len(matched)} of {len(job_skills)} detected job skills match your resume."
        )
    else:
        reasons.append("No direct skill overlap was detected.")
    if role_similarity >= 0.99:
        reasons.append("The internship title matches one of your target role categories.")
    elif role_similarity > 0:
        reasons.append("The internship title is partially similar to your target roles.")
    else:
        reasons.append("The internship title does not closely match your target roles.")
    if evidence_skills:
        reasons.append("Your experience or projects demonstrate some matching skills.")

    warnings = []
    if not job_skills:
        warnings.append("No recognizable skills were found in this listing.")
    if work_mode == "unknown":
        warnings.append("Work mode is unknown; verify it before applying.")
    if profile.parsing.get("requires_review", False):
        warnings.append("Review the extracted resume profile before relying on this score.")

    return {
        **job,
        "match_score": score,
        "match_level": "strong" if score >= 75 else "moderate" if score >= 50 else "low",
        "score_breakdown": {
            "skills": {"score": round(skill_points, 2), "max_points": 50},
            "role_relevance": {"score": round(role_points, 2), "max_points": 25},
            "experience_evidence": {
                "score": round(experience_points, 2),
                "max_points": 15,
            },
            "preferences": {"score": round(preference_points, 2), "max_points": 10},
        },
        "matching_skills": sorted(_display_skill(skill) for skill in matched),
        "missing_skills": sorted(_display_skill(skill) for skill in missing),
        "detected_job_skills": sorted(_display_skill(skill) for skill in job_skills),
        "experience_evidence_skills": sorted(
            _display_skill(skill) for skill in evidence_skills
        ),
        "reasons": reasons,
        "warnings": warnings,
    }


def match_jobs(
    profile: CandidateProfile,
    preferences: MatchingPreferences,
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Filter and rank captured jobs against a candidate profile."""

    eligible = []
    excluded_count = 0
    for job in jobs:
        if preferences.paid_only and job.get("stipend_status") != "paid":
            excluded_count += 1
            continue

        amount = job.get("stipend_amount")
        if amount is not None and amount < preferences.minimum_stipend_amount:
            excluded_count += 1
            continue

        mode = job.get("work_mode", "unknown")
        # Unknown modes remain visible for manual verification; known modes
        # outside the user's accepted list are filtered out.
        if preferences.work_modes and mode != "unknown" and mode not in preferences.work_modes:
            excluded_count += 1
            continue

        eligible.append(_match_one(profile, preferences, job))

    eligible.sort(key=lambda item: (-item["match_score"], item.get("captured_at", "")))

    return {
        "count": len(eligible),
        "excluded_count": excluded_count,
        "preferences_applied": preferences.model_dump(),
        "jobs": eligible,
        "note": (
            "Scores are transparent rule-based estimates, not hiring predictions. "
            "Review the listing and extracted resume profile before applying."
        ),
    }
