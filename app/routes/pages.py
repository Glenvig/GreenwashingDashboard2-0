from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from .. import crud
from ..db import get_pool
from ..schemas import MatchOut

router = APIRouter(prefix="/pages", tags=["pages"])


@router.get("/{page_id}/matches", response_model=list[MatchOut])
async def list_matches(page_id: UUID) -> list[MatchOut]:
    """Return all keyword matches found on a specific page, ordered by position."""
    pool = await get_pool()
    page = await crud.get_page(pool, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    rows = await crud.list_matches(pool, page_id)
    return [MatchOut(**r) for r in rows]
