"""
Greenwashing Dashboard – Crawler Service
========================================

Run locally:
    uvicorn app.main:app --reload

Environment variables (see .env.example):
    DATABASE_URL        asyncpg-compatible Postgres DSN
    CRAWL_CONCURRENCY   max simultaneous page fetches  (default 8)
    REQUEST_TIMEOUT     HTTP timeout in seconds         (default 15.0)
    MAX_PAGES_PER_RUN   crawl depth cap per run         (default 500)
    SNIPPET_CONTEXT     chars of context around match   (default 120)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .db import close_pool, get_pool
from .routes import pages, runs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s – %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Warm up the connection pool on startup.
    await get_pool()
    yield
    # Release all connections on shutdown.
    await close_pool()


app = FastAPI(
    title="Greenwashing Dashboard – Crawler Service",
    description=(
        "Async web crawler that scans domains for greenwashing keywords "
        "and stores matches in Postgres."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(runs.router)
app.include_router(pages.router)
