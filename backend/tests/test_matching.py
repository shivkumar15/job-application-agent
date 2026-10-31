from fastapi.testclient import TestClient

from app.integrations.internshala import InternshalaJobCreate
from app.main import app, job_store
from app.matching import CandidateProfile, MatchingPreferences, match_jobs

client = TestClient(app)


def candidate_profile():
    return CandidateProfile(
        skills=["React.js", "Node.js", "Express", "MongoDB", "JavaScript", "Python"],
        experience={
            "section_text": (
                "Built React.js interfaces and integrated REST APIs using JavaScript."
            )
        },
        projects={
            "section_text": (
                "Developed a MERN application with React.js, Node.js, Express and MongoDB."
            )
        },
        parsing={"requires_review": True},
    )


def sample_job(**overrides):
    payload = {
        "title": "MERN Stack Developer Intern",
        "company": "Example Technologies",
        "description": (
            "Build web applications using React, Node.js, Express and MongoDB. "
            "Work with JavaScript and REST APIs."
        ),
        "apply_url": "https://internshala.com/internship/detail/matching-test/",
        "location": "Remote",
        "work_mode": "remote",
        "stipend_status": "paid",
        "stipend_amount": 5000,
        "stipend_period": "month",
        "skills": ["React", "Node.js", "Express", "MongoDB", "JavaScript"],
        "captured_at": "2026-10-31T10:30:21+00:00",
        "dedupe_key": "test-key",
        "source": "internshala",
        "status": "discovered",
    }
    payload.update(overrides)
    return payload


def test_matching_returns_explainable_score_and_skill_evidence():
    result = match_jobs(
        candidate_profile(),
        MatchingPreferences(),
        [sample_job()],
    )
    assert result["count"] == 1
    match = result["jobs"][0]
    assert match["match_score"] >= 75
    assert match["match_level"] == "strong"
    assert "React.js" in match["matching_skills"]
    assert "Node.js" in match["matching_skills"]
    assert match["score_breakdown"]["skills"]["max_points"] == 50
    assert match["experience_evidence_skills"]


def test_paid_only_preference_excludes_unpaid_jobs():
    result = match_jobs(
        candidate_profile(),
        MatchingPreferences(paid_only=True),
        [sample_job(stipend_status="unpaid", stipend_amount=None)],
    )
    assert result["count"] == 0
    assert result["excluded_count"] == 1


def test_known_unaccepted_work_mode_is_excluded():
    result = match_jobs(
        candidate_profile(),
        MatchingPreferences(work_modes=["remote"]),
        [sample_job(work_mode="onsite")],
    )
    assert result["count"] == 0
    assert result["excluded_count"] == 1


def test_unknown_work_mode_is_kept_with_warning():
    result = match_jobs(
        candidate_profile(),
        MatchingPreferences(),
        [sample_job(work_mode="unknown")],
    )
    assert result["count"] == 1
    assert any("Work mode is unknown" in item for item in result["jobs"][0]["warnings"])


def test_stipend_minimum_is_applied():
    result = match_jobs(
        candidate_profile(),
        MatchingPreferences(minimum_stipend_amount=6000),
        [sample_job(stipend_amount=5000)],
    )
    assert result["count"] == 0
    assert result["excluded_count"] == 1


def test_matching_endpoint_uses_captured_jobs(monkeypatch):
    job_store._jobs.clear()
    created = InternshalaJobCreate(
        title="MERN Stack Developer Intern",
        company="Example Technologies",
        description="Build apps with React, Node.js, Express and MongoDB.",
        apply_url="https://internshala.com/internship/detail/api-matching-test/",
        location="Remote",
        work_mode="remote",
        stipend_status="paid",
        stipend_amount=5000,
        stipend_period="month",
        skills=["React", "Node.js", "Express", "MongoDB"],
    )
    job_store.create(created)

    response = client.post(
        "/api/v1/matching/jobs",
        json={
            "candidate_profile": candidate_profile().model_dump(),
            "preferences": {
                "target_roles": [
                    "MERN Stack Developer Intern",
                    "Full Stack Developer Intern",
                ],
                "paid_only": True,
                "work_modes": ["remote", "onsite"],
                "minimum_stipend_amount": 0,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["jobs"][0]["match_score"] > 0
    job_store._jobs.clear()
