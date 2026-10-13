#!/usr/bin/env python3
"""Set up the agent_fetches table in the Nile database (PRD D5, bot logging).

Tom runs this ONCE, by hand, before (or right after) deploying the
agent-fetch function:

    python3 scripts/setup_agent_fetches.py

Safe to re-run (CREATE ... IF NOT EXISTS). Until it has run, the function
still serves /about/agent/ and /llms.txt; its inserts just fail with a
console warning.

One row per fetch of an agent surface. No IP address, no query strings,
nothing from the request body (PRD guardrail 8).
"""

import os
import psycopg2
from db_target import resolve_db



def setup_agent_fetches():
    conn = psycopg2.connect(resolve_db('create the agent_fetches table in'))
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS agent_fetches (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            path TEXT,
            user_agent TEXT,
            referer TEXT NULL,
            country TEXT NULL,
            status INT
        )
    ''')

    # 2026-10-12: meta (counts, role shape, asker, send tag; never text) for
    # /ask and /ask/brief rows and tagged start.md fetches.
    cur.execute('''
        ALTER TABLE agent_fetches ADD COLUMN IF NOT EXISTS meta JSONB
    ''')
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_agent_fetches_path ON agent_fetches(path)
    ''')

    # Index for querying by date
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_agent_fetches_created_at
        ON agent_fetches(created_at DESC)
    ''')

    conn.commit()
    print("✓ agent_fetches table created")

    cur.close()
    conn.close()


if __name__ == '__main__':
    setup_agent_fetches()
