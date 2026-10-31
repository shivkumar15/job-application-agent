import re
from pathlib import Path
from pydantic import ValidationError
from app.resume_parser import _internship_count, SKILL_TERMS
from app.integrations.internshala import InternshalaJobCreate, InternshalaJobStore

sample = "Machine Learning InternMar 2026 – May 2026\nNIELIT\nFull Stack Web Development InternJune 2025\nAndrowebstech"
assert _internship_count(sample) == 2, _internship_count(sample)
assert {"React", "React.js"} <= set(SKILL_TERMS)
base = {
"title": "Full Stack Development Intern",
"company": "Example Technologies",
"description": "Build web applications using React, Node.js and MongoDB. Work with APIs.",
"apply_url": "https://internshala.com/internship/detail/example-listing/",
"location": "Remote",
"work_mode": "remote",
"stipend_status": "paid",
"stipend_amount": 5000,
"stipend_period": "month",
}
job = InternshalaJobCreate(**base)
store = InternshalaJobStore()
saved = store.create(job)
assert saved["stipend_status"] == "paid"
assert len(store.list_jobs(paid_only=True)) == 1
try:
    store.create(job)
    raise AssertionError("duplicate was accepted")
except KeyError:
    pass
try:
    InternshalaJobCreate(**{**base, "apply_url":"https://example.com/job"})
    raise AssertionError("foreign url was accepted")
except ValidationError:
    pass
try:
    InternshalaJobCreate(**{**base, "stipend_amount":None})
    raise AssertionError("paid listing without amount was accepted")
except ValidationError:
    pass
print("Local focused checks passed")
