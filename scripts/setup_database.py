#!/usr/bin/env python3
"""Set up the database schema for TomBot RAG.

Schema based on: docs/tombot/RAG/cv-chatbot-rag-schema.md
"""

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()


def setup_schema():
    db_url = os.getenv("NILEDB_URL")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    print("Dropping existing tables...")
    cur.execute("DROP TABLE IF EXISTS chunks;")
    cur.execute("DROP TABLE IF EXISTS aliases;")
    conn.commit()

    print("Creating TomBot RAG schema...")

    # Create chunks table per cv-chatbot-rag-schema.md
    # Single table for fast retrieval - no JOINs at query time
    cur.execute("""
        CREATE TABLE chunks (
            -- Identity
            id              VARCHAR(30) PRIMARY KEY,
            chunk_type      VARCHAR(20) NOT NULL,

            -- The actual content (this is what Claude sees)
            title           VARCHAR(200),
            content         TEXT NOT NULL,

            -- The embedding (this is what we search) - voyage-3 uses 1024 dims
            embedding       vector(1024) NOT NULL,

            -- Denormalised context (baked in at load time, no JOINs needed)
            company_name    VARCHAR(100),
            role_title      VARCHAR(150),
            years_start     INTEGER,
            years_end       INTEGER,

            -- For tricky_questions: embed the question too for matching
            question_text   TEXT,
            question_embedding vector(1024),

            -- For stories: question patterns this answers
            good_for        TEXT[],

            -- Metadata
            tags            TEXT[],
            source_file     VARCHAR(100),

            created_at      TIMESTAMP DEFAULT NOW()
        );
    """)

    # Primary index: vector similarity search on content
    cur.execute("""
        CREATE INDEX idx_chunks_embedding ON chunks
            USING ivfflat(embedding vector_cosine_ops)
            WITH (lists = 10);
    """)

    # Secondary index: question matching for tricky_questions
    cur.execute("""
        CREATE INDEX idx_chunks_question_embedding ON chunks
            USING ivfflat(question_embedding vector_cosine_ops)
            WITH (lists = 10)
            WHERE question_embedding IS NOT NULL;
    """)

    # Filter indexes
    cur.execute("CREATE INDEX idx_chunks_type ON chunks(chunk_type);")
    cur.execute("CREATE INDEX idx_chunks_years ON chunks(years_start, years_end);")
    cur.execute("CREATE INDEX idx_chunks_tags ON chunks USING GIN(tags);")

    # Aliases table for resolving "Novo" -> "Novo Nordisk" etc
    cur.execute("""
        CREATE TABLE aliases (
            alias           VARCHAR(100) PRIMARY KEY,
            canonical_name  VARCHAR(100) NOT NULL,
            alias_type      VARCHAR(20) NOT NULL
        );
    """)

    conn.commit()
    print("Schema created successfully!")

    # Show tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    tables = cur.fetchall()
    print(f"   Tables: {[t[0] for t in tables]}")

    # Show chunks columns
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'chunks'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    print("   Chunks columns:")
    for col, dtype in columns:
        print(f"      - {col}: {dtype}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    setup_schema()
