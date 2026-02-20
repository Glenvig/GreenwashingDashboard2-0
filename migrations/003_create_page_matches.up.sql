-- Migration: 003_create_page_matches (UP)
-- One row per keyword occurrence found on a page.
-- Uses BIGINT identity (not UUID) because this table can be very large
-- and integer PKs are cheaper to index and join on at high volume.

CREATE TABLE page_matches (
    id           BIGINT  NOT NULL GENERATED ALWAYS AS IDENTITY,
    page_id      UUID    NOT NULL,
    keyword      TEXT    NOT NULL,
    matched_text TEXT    NOT NULL,
    tag          TEXT,           -- HTML element where the match was found (e.g. 'h1', 'p', 'a')
    position     INTEGER,        -- Character offset within the page source
    snippet      TEXT,           -- Short surrounding context for display

    CONSTRAINT page_matches_pkey
        PRIMARY KEY (id),

    CONSTRAINT page_matches_page_id_fkey
        FOREIGN KEY (page_id)
        REFERENCES pages (id)
        ON DELETE CASCADE
);

-- All matches for a given page (most common read pattern)
CREATE INDEX idx_page_matches_page_id
    ON page_matches (page_id);

-- Cross-page keyword aggregation / reporting
CREATE INDEX idx_page_matches_keyword
    ON page_matches (keyword);

-- Targeted lookup: all occurrences of a keyword on a specific page
CREATE INDEX idx_page_matches_page_id_keyword
    ON page_matches (page_id, keyword);
