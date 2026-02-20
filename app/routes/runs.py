from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..crawler import crawl_run
from .. import crud
from ..db import get_pool
from ..schemas import PageOut, RunCreate, RunOut

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
async def create_run(body: RunCreate, background_tasks: BackgroundTasks) -> RunOut:
    """
    Create a crawl run and immediately start the background crawl.

    The response reflects the freshly-inserted row (status='pending').
    The crawl transitions it to 'running' within milliseconds.
    """
    pool = await get_pool()
    run_id = await crud.create_run(pool, domain=body.domain, created_by="api")

    background_tasks.add_task(
        crawl_run,
        run_id=run_id,
        domain=body.domain,
        keywords=body.keywords,
        excludes=body.excludes,
        pool=pool,
    )

    row = await crud.get_run(pool, run_id)
    return RunOut(**row)  # type: ignore[arg-type]


@router.get("", response_model=list[RunOut])
async def list_runs() -> list[RunOut]:
    """Return all crawl runs, newest first."""
    pool = await get_pool()
    rows = await crud.list_runs(pool)
    return [RunOut(**r) for r in rows]


@router.get("/{run_id}/pages", response_model=list[PageOut])
async def list_pages(run_id: UUID) -> list[PageOut]:
    """Return all pages discovered within a given run, ordered by URL."""
    pool = await get_pool()
    run = await crud.get_run(pool, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = await crud.list_pages(pool, run_id)
    return [PageOut(**r) for r in rows]
