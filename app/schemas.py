from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, field_validator


class RunCreate(BaseModel):
    domain: str
    keywords: list[str]
    excludes: list[str] = []

    @field_validator("domain")
    @classmethod
    def strip_domain(cls, v: str) -> str:
        return v.strip().rstrip("/")

    @field_validator("keywords", "excludes")
    @classmethod
    def non_empty_strings(cls, v: list[str]) -> list[str]:
        return [k.strip() for k in v if k.strip()]


class RunOut(BaseModel):
    id: UUID
    created_at: datetime
    created_by: str
    domain: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    pages_found: int
    pages_scanned: int
    error_count: int

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    id: UUID
    run_id: UUID
    url: str
    status: str
    total_hits: int
    keywords_csv: Optional[str] = None
    last_scanned_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class MatchOut(BaseModel):
    id: int
    page_id: UUID
    keyword: str
    matched_text: str
    tag: Optional[str] = None
    position: Optional[int] = None
    snippet: Optional[str] = None

    model_config = {"from_attributes": True}
