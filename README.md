# Job Application Agent

A cloud-hosted assistant for discovering internships, evaluating fit, preparing applications, and tracking applications. Application submission always requires the user's explicit approval.

## Current scope

- **Phase 1 — Resume intelligence:** Upload a text-based PDF resume, extract a reviewable candidate profile, normalize skills, and expose health/API docs.
- **Phase 2 — Internshala manual capture:** Save Internshala listings that the user has selected and manually provided. This integration does not scrape Internshala, automate website access, log in, or submit applications.
- **Phase 3 — Job matching:** Rank captured listings against a reviewed resume profile using explainable skill, role, experience-evidence, and preference scores.
- **Phase 4 — Application material:** Prepare template-based cover letters, application emails, and resume-tailoring guidance for a selected captured listing. Drafts use only supplied profile/listing data and are never sent automatically.

> **Platform compliance:** Use Internshala through its normal user-facing website. This project does not crawl, scrape, bypass access controls, or automate access to Internshala. Check current platform terms and obtain written permission before building any automated site access.

## Requirements

- Python 3.11+
- pip

## Run locally (Windows PowerShell, recommended virtual environment)

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

When reopening the terminal, activate the environment again with `.\.venv\Scripts\Activate.ps1`. The `.venv` directory is excluded from Git.

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

## Phase 3 — Resume-to-job matching

1. Analyze a resume with `POST /api/v1/resumes/analyze`.
2. Review the returned `profile` fields.
3. Send that profile and matching preferences to `POST /api/v1/matching/jobs`.
4. The API ranks the captured listings and explains matching skills, missing skills, score components, and warnings.

The matching endpoint is stateless: it does not save the candidate profile or resume. It uses the listings currently available in the job store. Scores are rule-based estimates, not hiring predictions. Jobs with unknown work mode remain visible with a warning so the user can verify them manually.

## Phase 4 — Tailored application material

1. Select a captured listing and copy its `dedupe_key` from the listing response.
2. Analyze your resume and review the returned `profile`.
3. Call `POST /api/v1/applications/prepare` with the selected `dedupe_key` and reviewed `candidate_profile`.
4. Review the generated cover letter, email subject/body, and resume guidance.
5. Replace `[Your Name]`, verify every statement, and make any edits before using the drafts.

Example request body:

```json
{
  "dedupe_key": "paste-the-selected-job-dedupe-key",
  "candidate_profile": {
    "skills": ["React.js", "Node.js", "Express", "MongoDB", "JavaScript"],
    "experience": {
      "section_text": "Paste the reviewed experience section from resume analysis."
    },
    "projects": {
      "section_text": "Paste the reviewed projects section from resume analysis."
    },
    "parsing": {
      "requires_review": true
    }
  }
}
```

This first version uses deterministic templates, not an external AI service. It highlights skills that overlap with the listing, separately identifies detected job skills not found in the resume, and only describes experience evidence when the profile sections mention the relevant skills. It does not invent qualifications, store the profile, email recruiters, or submit applications. The endpoint returns `submission_status: draft_only`.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health |
| POST | `/api/v1/resumes/analyze` | Extract resume profile from PDF |
| GET | `/api/v1/integrations/internshala/status` | Integration mode and storage |
| POST | `/api/v1/integrations/internshala/jobs` | Manually capture a listing |
| GET | `/api/v1/integrations/internshala/jobs` | List captured listings |
| GET | `/api/v1/integrations/internshala/jobs/{dedupe_key}` | Retrieve one captured listing |
| POST | `/api/v1/matching/jobs` | Rank captured listings against a resume profile |
| POST | `/api/v1/applications/prepare` | Prepare application drafts for a captured listing |

## Tests

From `backend/`:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover parser behavior, input validation, filtering, duplicate prevention, and application draft generation. They do not test live Internshala retrieval because no automated site access is performed.

## Deployment notes

Deploy the backend as a Python/Docker web service. Set `MAX_UPLOAD_MB`, `CORS_ORIGINS`, `MONGODB_URI`, and `MONGODB_DATABASE` as environment variables. Add authentication and per-user data isolation before exposing uploads or job records publicly.

## Roadmap

- Phase 5: Approval workflow and permitted submission assistance.
- Phase 6: Dashboard, email notifications and daily discovery from permitted sources.
- Phase 7: Cloud scheduling, monitoring and deployment hardening.
