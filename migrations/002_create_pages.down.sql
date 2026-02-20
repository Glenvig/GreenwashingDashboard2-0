-- Migration: 002_create_pages (DOWN)

DROP TABLE IF EXISTS pages CASCADE;
DROP TYPE  IF EXISTS page_status;
