#!/usr/bin/env python3
"""Set up error_logs table in Nile database."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def setup_error_logs():
    conn = psycopg2.connect(os.environ['NILEDB_URL'])
    cur = conn.cursor()

    # Create error_logs table - one row per failed request
    cur.execute('''
        CREATE TABLE IF NOT EXISTS error_logs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            session_id TEXT,
            query TEXT,
            error TEXT
        )
    ''')

    # Index for querying by date
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_error_logs_created_at
        ON error_logs(created_at DESC)
    ''')

    conn.commit()
    print("✓ error_logs table created")

    cur.close()
    conn.close()

if __name__ == '__main__':
    setup_error_logs()
