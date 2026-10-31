from fastapi.testclient import TestClient

from app.integrations.internshala import InternshalaJobCreate
from app.main import app, job_store

client = TestClient(app)


def profile_payload():
    return {
        "skills": ["React.js", "Node.js", "Express", "MongoDB", "JavaScript"],
        "experience": {
            "section_text": "Built React.js interfaces and integrated REST APIs."
        },
        "projects": {
            "section_text": "Developed a MERN project using Node.js, Express and MongoDB."
        },
        "parsing": {"requires_review": True},
    }


def create_job():
    return job_store.create(
        InternshalaJobCreate(
            title="MERN Stack Developer Intern",
            company="Example Technologies",
            description="Build applications using React, Node.js, Express, MongoDB and TypeScript.",
            apply_url="https://internshala.com/internship/detail/application-material-test/",
            location="Remote",
            work_mode="remote",
            stipend_status="paid",
            stipend_amount=5000,
            stipend_period="month",
            skills=["React", "Node.js", "Express", "MongoDB", "TypeScript"],
        )
    )


def test_prepare_application_material_returns_drafts_without_submitting():
    job_store._jobs.clear()
    job = create_job()
    response = client.post(
        "/api/v1/applications/prepare",
        json={
            "dedupe_key": job["dedupe_key"],
            "candidate_profile": profile_payload(),
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["submission_status"] == "draft_only"
    assert result["job"]["company"] == "Example Technologies"
    assert "React.js" in result["resume_guidance"]["skills_to_highlight"]
    assert "TypeScript" in result["resume_guidance"]["skills_not_found_in_resume"]
    assert "[Your Name]" in result["cover_letter"]
    assert "Nothing has been sent" in result["note"]
    job_store._jobs.clear()


def test_prepare_application_material_rejects_unknown_job():
    job_store._jobs.clear()
    response = client.post(
        "/api/v1/applications/prepare",
        json={
            "dedupe_key": "a" * 64,
            "candidate_profile": profile_payload(),
        },
    )
    assert response.status_code == 404
    job_store._jobs.clear()


def test_prepare_application_material_does_not_claim_unproven_experience():
    job_store._jobs.clear()
    job = create_job()
    response = client.post(
        "/api/v1/applications/prepare",
        json={
            "dedupe_key": job["dedupe_key"],
            "candidate_profile": {
                "skills": ["React.js", "Node.js"],
                "experience": {},
                "projects": {},
            },
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["resume_guidance"]["evidence_skills"] == []
    assert "experience and project sections specifically mention" not in result["cover_letter"]
    job_store._jobs.clear()
