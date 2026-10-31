from fastapi.testclient import TestClient

from app.main import app, job_store

client = TestClient(app)


def sample_job(**overrides):
    data = {
        "title": "Full Stack Development Intern",
        "company": "Example Technologies",
        "description": (
            "Build web applications using React, Node.js and MongoDB. "
            "Work with APIs and collaborate with the engineering team."
        ),
        "apply_url": "https://internshala.com/internship/detail/example-listing/",
        "location": "Remote",
        "work_mode": "remote",
        "stipend_status": "paid",
        "stipend_amount": 5000,
        "stipend_period": "month",
        "stipend_display": "5000/month",
        "skills": ["React", "Node.js", "MongoDB"],
        "deadline": "2026-11-15",
    }
    data.update(overrides)
    return data


def test_status_reports_manual_capture():
    response = client.get("/api/v1/integrations/internshala/status")
    assert response.status_code == 200
    assert response.json()["integration_mode"] == "manual_capture"
    assert response.json()["automated_site_access"] is False


def test_create_and_list_paid_job():
    job_store._jobs.clear()
    response = client.post("/api/v1/integrations/internshala/jobs", json=sample_job())
    assert response.status_code == 201
    assert response.json()["source"] == "internshala"

    listing = client.get("/api/v1/integrations/internshala/jobs?paid_only=true")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1


def test_duplicate_job_is_rejected():
    job_store._jobs.clear()
    first = client.post("/api/v1/integrations/internshala/jobs", json=sample_job())
    second = client.post("/api/v1/integrations/internshala/jobs", json=sample_job())
    assert first.status_code == 201
    assert second.status_code == 409


def test_non_internshala_url_is_rejected():
    response = client.post(
        "/api/v1/integrations/internshala/jobs",
        json=sample_job(apply_url="https://example.com/job"),
    )
    assert response.status_code == 422


def test_unpaid_job_excluded_from_paid_filter():
    job_store._jobs.clear()
    payload = sample_job(
        title="Frontend Intern",
        apply_url="https://internshala.com/internship/detail/unpaid-listing/",
        stipend_status="unpaid",
        stipend_amount=None,
        stipend_period=None,
        stipend_display="Unpaid",
    )
    response = client.post("/api/v1/integrations/internshala/jobs", json=payload)
    assert response.status_code == 201
    listing = client.get("/api/v1/integrations/internshala/jobs?paid_only=true")
    assert listing.json()["count"] == 0


def test_paid_job_requires_amount():
    payload = sample_job(stipend_amount=None)
    response = client.post("/api/v1/integrations/internshala/jobs", json=payload)
    assert response.status_code == 422


def test_work_mode_filter():
    job_store._jobs.clear()
    client.post("/api/v1/integrations/internshala/jobs", json=sample_job())
    hybrid = sample_job(
        title="React Intern",
        company="Another Company",
        apply_url="https://internshala.com/internship/detail/hybrid-listing/",
        work_mode="hybrid",
    )
    client.post("/api/v1/integrations/internshala/jobs", json=hybrid)
    response = client.get("/api/v1/integrations/internshala/jobs?work_mode=hybrid")
    assert response.json()["count"] == 1


def test_get_missing_job_returns_404():
    response = client.get("/api/v1/integrations/internshala/jobs/not-a-real-key")
    assert response.status_code == 404
