-- Migration: 002_create_pages (UP)
-- One row per URL discovered within a crawl run.

CREATE TYPE page_status AS ENUM (
    'pending',
    'scanning',
    'completed',
    'failed',
    'skipped'
);

CREATE TABLE pages (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    run_id          UUID        NOT NULL,
    url             TEXT        NOT NULL,
    status          page_status NOT NULL DEFAULT 'pending',
    assigned_to     TEXT,
    notes           TEXT,
    total_hits      INTEGER     NOT NULL DEFAULT 0,
    keywords_csv    TEXT,
    last_scanned_at TIMESTAMPTZ,

    CONSTRAINT pages_pkey
        PRIMARY KEY (id),

    CONSTRAINT pages_run_id_fkey
        FOREIGN KEY (run_id)
        REFERENCES crawl_runs (id)
        ON DELETE CASCADE,

    CONSTRAINT pages_total_hits_non_negative
        CHECK (total_hits >= 0)
);

-- Main FK lookup: all pages belonging to a run
CREATE INDEX idx_pages_run_id
    ON pages (run_id);

-- Cross-run URL lookup (e.g. "has this URL been seen before?")
CREATE INDEX idx_pages_url
    ON pages (url);

-- Worker queue: grab pending pages for a specific run
CREATE INDEX idx_pages_run_id_status
    ON pages (run_id, status);

-- Prevent the same URL appearing twice in one run
CREATE UNIQUE INDEX idx_pages_run_id_url
    ON pages (run_id, url);
