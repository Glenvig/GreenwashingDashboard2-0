-- Migration: 001_create_crawl_runs (UP)
-- Creates the top-level table that represents a single crawl job.

-- gen_random_uuid() is built-in since Postgres 13.
-- For Postgres < 13 uncomment the next line:
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE crawl_run_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'cancelled'
);

CREATE TABLE crawl_runs (
    id             UUID             NOT NULL DEFAULT gen_random_uuid(),
    created_at     TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    created_by     TEXT             NOT NULL,
    domain         TEXT             NOT NULL,
    status         crawl_run_status NOT NULL DEFAULT 'pending',
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    pages_found    INTEGER          NOT NULL DEFAULT 0,
    pages_scanned  INTEGER          NOT NULL DEFAULT 0,
    error_count    INTEGER          NOT NULL DEFAULT 0,

    CONSTRAINT crawl_runs_pkey
        PRIMARY KEY (id),

    CONSTRAINT crawl_runs_pages_found_non_negative
        CHECK (pages_found  >= 0),

    CONSTRAINT crawl_runs_pages_scanned_non_negative
        CHECK (pages_scanned >= 0),

    CONSTRAINT crawl_runs_error_count_non_negative
        CHECK (error_count   >= 0),

    CONSTRAINT crawl_runs_finished_after_started
        CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at)
);

-- Filter / group runs by domain
CREATE INDEX idx_crawl_runs_domain
    ON crawl_runs (domain);

-- Queue-style queries: WHERE status = 'running'
CREATE INDEX idx_crawl_runs_status
    ON crawl_runs (status);

-- Chronological listing
CREATE INDEX idx_crawl_runs_created_at
    ON crawl_runs (created_at DESC);

-- Per-user history
CREATE INDEX idx_crawl_runs_created_by
    ON crawl_runs (created_by);
