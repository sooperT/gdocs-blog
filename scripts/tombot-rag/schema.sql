-- TomBot RAG Database Schema
-- For use with Nile (PostgreSQL with pgvector)

-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- MAIN CHUNKS TABLE
-- ============================================================================
-- Single denormalised table for efficient retrieval
-- All content is baked into each chunk - no JOINs needed at query time

CREATE TABLE IF NOT EXISTS chunks (
    -- Identity
    id              VARCHAR(30) PRIMARY KEY,        -- e.g. 'role_R16', 'story_S04', 'tq_TQ08'
    chunk_type      VARCHAR(20) NOT NULL,           -- 'role', 'story', 'tricky_question', 'competency', 'theme', 'basic_info'

    -- The actual content (this is what Claude sees)
    title           VARCHAR(200),
    content         TEXT NOT NULL,

    -- The embedding (this is what we search)
    embedding       VECTOR(1024) NOT NULL,          -- Voyage AI voyage-3 uses 1024 dimensions

    -- Denormalised context (baked in at load time, no JOINs needed)
    company_name    VARCHAR(100),
    role_title      VARCHAR(150),
    years_start     INTEGER,
    years_end       INTEGER,

    -- For special retrieval logic
    question_text   TEXT,                           -- For tricky_questions: the question itself
    question_embedding VECTOR(1024),                -- Embed the question too for matching
    good_for        TEXT[],                         -- For stories: question patterns this answers

    -- Metadata
    tags            TEXT[],
    source_file     VARCHAR(100),

    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Primary index: vector similarity search on content embedding
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks
    USING ivfflat(embedding vector_cosine_ops)
    WITH (lists = 10);  -- Small dataset, fewer lists

-- Secondary index: question matching for tricky_questions
CREATE INDEX IF NOT EXISTS idx_chunks_question_embedding ON chunks
    USING ivfflat(question_embedding vector_cosine_ops)
    WITH (lists = 10)
    WHERE question_embedding IS NOT NULL;

-- Filter indexes (for hybrid queries if needed)
CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_years ON chunks(years_start, years_end);
CREATE INDEX IF NOT EXISTS idx_chunks_company ON chunks(company_name);

-- ============================================================================
-- ALIASES TABLE
-- ============================================================================
-- For resolving common abbreviations and alternative names

CREATE TABLE IF NOT EXISTS aliases (
    alias           VARCHAR(100) PRIMARY KEY,       -- The shorthand people use
    canonical_name  VARCHAR(100) NOT NULL,          -- The full name
    alias_type      VARCHAR(20) NOT NULL            -- 'company', 'product', 'project'
);

-- Case-insensitive lookup index
CREATE INDEX IF NOT EXISTS idx_aliases_lower ON aliases(LOWER(alias));

-- ============================================================================
-- SAMPLE QUERIES (for reference)
-- ============================================================================

-- Basic semantic search (find top 5 most similar chunks):
-- SELECT id, title, content, chunk_type,
--        1 - (embedding <=> $1) as similarity
-- FROM chunks
-- ORDER BY embedding <=> $1
-- LIMIT 5;

-- Tricky question matching (check for high-similarity match):
-- SELECT id, title, content,
--        1 - (question_embedding <=> $1) as q_similarity
-- FROM chunks
-- WHERE chunk_type = 'tricky_question'
--   AND question_embedding IS NOT NULL
-- ORDER BY question_embedding <=> $1
-- LIMIT 1;

-- Filter by time period:
-- SELECT id, title, content
-- FROM chunks
-- WHERE years_start <= 2020 AND years_end >= 2020
-- ORDER BY embedding <=> $1
-- LIMIT 5;

-- Alias lookup:
-- SELECT canonical_name
-- FROM aliases
-- WHERE LOWER(alias) = LOWER($1);
