import hashlib
import os
from datetime import datetime, timezone
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

try:
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError
except ImportError:  # pragma: no cover
    MongoClient = None
    DuplicateKeyError = Exception


class InternshalaJobCreate(BaseModel):
    """A listing manually entered by the user from Internshala's normal website."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    company: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=20, max_length=12000)
    apply_url: str
    location: str = Field(min_length=2, max_length=180)
    work_mode: Literal["remote", "onsite", "hybrid", "unknown"] = "unknown"
    stipend_status: Literal["paid", "unpaid", "unknown"]
    stipend_amount: Optional[float] = Field(default=None, ge=0, le=1000000)
    stipend_period: Optional[Literal["month", "week", "day", "year", "one-time"]] = None
    stipend_display: Optional[str] = Field(default=None, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=40)
    deadline: Optional[str] = None

    @field_validator("apply_url")
    @classmethod
    def validate_internshala_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"internshala.com", "www.internshala.com"}
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("apply_url must be a genuine HTTPS Internshala URL.")
        return value

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("deadline must use YYYY-MM-DD format.") from exc
        return value

    @model_validator(mode="after")
    def validate_stipend(self):
        if self.stipend_status == "paid" and self.stipend_amount is None:
            raise ValueError("stipend_amount is required when stipend_status is paid.")
        if self.stipend_status != "paid" and self.stipend_amount is not None:
            raise ValueError("stipend_amount must be omitted unless stipend_status is paid.")
        return self


class InternshalaJobStore:
    def __init__(self, mongo_uri: Optional[str] = None, database: Optional[str] = None):
        self._jobs = {}
        self._client = None
        self._collection = None
        mongo_uri = mongo_uri or os.getenv("MONGODB_URI")
        database = database or os.getenv("MONGODB_DATABASE", "job_application_agent")
        if mongo_uri:
            if MongoClient is None:
                raise RuntimeError("pymongo is required when MONGODB_URI is configured.")
            self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self._collection = self._client[database]["internshala_jobs"]
            self._collection.create_index("dedupe_key", unique=True)

    @property
    def storage_mode(self) -> str:
        return "mongodb" if self._collection is not None else "in_memory"

    @staticmethod
    def _dedupe_key(payload: dict) -> str:
        canonical_url = payload["apply_url"].split("?")[0].rstrip("/").lower()
        raw = f"{canonical_url}|{payload['title'].casefold()}|{payload['company'].casefold()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create(self, job: InternshalaJobCreate) -> dict:
        payload = job.model_dump()
        dedupe_key = self._dedupe_key(payload)
        document = {
            **payload,
            "source": "internshala",
            "dedupe_key": dedupe_key,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "status": "discovered",
        }
        if self._collection is not None:
            try:
                self._collection.insert_one(document)
            except DuplicateKeyError as exc:
                raise KeyError(dedupe_key) from exc
        else:
            if dedupe_key in self._jobs:
                raise KeyError(dedupe_key)
            self._jobs[dedupe_key] = document
        return document

    def list_jobs(self, paid_only: bool = False, work_mode: Optional[str] = None) -> list[dict]:
        if self._collection is not None:
            query = {}
            if paid_only:
                query["stipend_status"] = "paid"
            if work_mode:
                query["work_mode"] = work_mode
            documents = list(self._collection.find(query, {"_id": 0}).sort("captured_at", -1))
        else:
            documents = list(self._jobs.values())
            if paid_only:
                documents = [job for job in documents if job["stipend_status"] == "paid"]
            if work_mode:
                documents = [job for job in documents if job["work_mode"] == work_mode]
            documents.sort(key=lambda job: job["captured_at"], reverse=True)
        return documents

    def get(self, dedupe_key: str) -> Optional[dict]:
        if self._collection is not None:
            return self._collection.find_one({"dedupe_key": dedupe_key}, {"_id": 0})
        return self._jobs.get(dedupe_key)


def build_store() -> InternshalaJobStore:
    return InternshalaJobStore()
