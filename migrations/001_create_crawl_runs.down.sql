-- Migration: 001_create_crawl_runs (DOWN)
-- Removes crawl_runs and its dependent objects.
-- CASCADE also drops pages and page_matches if they still exist
-- (in case down migrations are run out of order).

DROP TABLE IF EXISTS crawl_runs CASCADE;
DROP TYPE  IF EXISTS crawl_run_status;
