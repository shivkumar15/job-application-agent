# Job Application Agent

A cloud-hosted assistant for discovering internships, evaluating fit, preparing applications, and tracking applications. Application submission always requires the user's explicit approval.

## Current scope

- **Phase 1 — Resume intelligence:** Upload a text-based PDF resume, extract a reviewable candidate profile, normalize skills, and expose health/API docs.
- **Phase 2 — Internshala manual capture:** Save Internshala listings that the user has selected and manually provided. This integration does not scrape Internshala, automate website access, log in, or submit applications.

> **Platform compliance:** Use Internshala through its normal user-facing website. This project does not crawl, scrape, bypass access controls, or automate access to Internshala. Check current platform terms and obtain written permission before building any automated site access.

## Requirements

- Python 3.11+
- pip

## Run locally (Windows PowerShell, no virtual environment)

From the repository root:

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open:
- Health: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs

## Phase 1 — Resume analysis

In Swagger, execute `POST /api/v1/resumes/analyze` and upload a text-based PDF (max 5 MB). The API returns extracted information for review and does not persist the resume or extracted PII.

Parsing is heuristic. Always review the profile before using details in an application. Scanned/image-only and password-protected PDFs are not supported.

## Phase 2 — Internshala manual capture

1. Find a listing through Internshala's normal website.
2. Copy its genuine listing URL and the details you can see.
3. Use `POST /api/v1/integrations/internshala/jobs` to save it.
4. Retrieve saved listings with `GET /api/v1/integrations/internshala/jobs`.

The default store is in-memory for local development; it clears on restart. Configure MongoDB for durable storage:

```powershell
$env:MONGODB_URI="mongodb+srv://<username>:<password>@<cluster>/<database>?retryWrites=true&w=majority"
$env:MONGODB_DATABASE="job_application_agent"
```

Restart the backend after setting environment variables. Never commit database credentials or resume files.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health |
| POST | `/api/v1/resumes/analyze` | Extract resume profile from PDF |
| GET | `/api/v1/integrations/internshala/status` | Integration mode and storage |
| POST | `/api/v1/integrations/internshala/jobs` | Manually capture a listing |
| GET | `/api/v1/integrations/internshala/jobs` | List captured listings |
| GET | `/api/v1/integrations/internshala/jobs/{dedupe_key}` | Retrieve one captured listing |

## Tests

From `backend/`:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover parser behavior, input validation, filtering and duplicate prevention. They do not test live Internshala retrieval because no automated site access is performed.

## Deployment notes

Deploy the backend as a Python/Docker web service. Set `MAX_UPLOAD_MB`, `CORS_ORIGINS`, `MONGODB_URI`, and `MONGODB_DATABASE` as environment variables. Add authentication and per-user data isolation before exposing uploads or job records publicly.

## Roadmap

- Phase 3: Resume-to-job relevance scoring.
- Phase 4: Tailored application material.
- Phase 5: Approval workflow and permitted submission assistance.
- Phase 6: Dashboard, email notifications and daily discovery from permitted sources.
- Phase 7: Cloud scheduling, monitoring and deployment hardening.
