#!/usr/bin/env python3
"""Set up chat_logs table in Nile database."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def setup_chat_logs():
    conn = psycopg2.connect(os.environ['NILEDB_URL'])
    cur = conn.cursor()

    # Create chat_logs table - one row per session
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_logs (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL UNIQUE,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            messages JSONB DEFAULT '[]'::jsonb,
            retrieval_log JSONB DEFAULT '[]'::jsonb
        )
    ''')

    # Index for querying by date
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_chat_logs_started_at
        ON chat_logs(started_at DESC)
    ''')

    conn.commit()
    print("✓ chat_logs table created")

    cur.close()
    conn.close()

if __name__ == '__main__':
    setup_chat_logs()
