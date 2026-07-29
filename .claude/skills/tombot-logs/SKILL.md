---
name: tombot-logs
description: Query TomBot chat logs, deflections and errors from the database
argument-hint: "[search <term> | today | yesterday | deflections | errors | <number of days>]"
allowed-tools: Bash, Read
---

# TomBot Log Viewer

Query the TomBot chat logs stored in the Nile Postgres database.

## Usage

- `/tombot-logs` — show sessions from the last 7 days
- `/tombot-logs today` — today's sessions only
- `/tombot-logs yesterday` — yesterday's sessions only
- `/tombot-logs 14` — last 14 days
- `/tombot-logs search <term>` — search user messages for a keyword
- `/tombot-logs deflections` — show recent deflected queries only
- `/tombot-logs errors` — show recent backend errors only

## How to query

Run a Python script using `python3 -c "..."` from the project root. Load the database URL from `.env`:

```python
import os, json, psycopg2
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['NILEDB_URL'])
cur = conn.cursor()
```

## Database schema

### `chat_logs` table
- `session_id` TEXT — unique session identifier
- `started_at` TIMESTAMPTZ — when the session started
- `updated_at` TIMESTAMPTZ — last activity
- `messages` JSONB — array of `{"user": "...", "assistant": "...", "timestamp": "..."}`
- `retrieval_log` JSONB — array of `{"method": "...", "matches": [{"section": "...", "score": 0.8}]}`

### `deflections` table
- `query` TEXT — the user's question that was deflected
- `top_match` TEXT — nearest knowledge base match
- `top_score` FLOAT — similarity score (deflected when < 0.55)
- `session_id` TEXT
- `created_at` TIMESTAMPTZ

### `error_logs` table
- `id` SERIAL
- `created_at` TIMESTAMPTZ — when the error happened
- `session_id` TEXT — chat session the error occurred in (may be NULL)
- `query` TEXT — the user question being answered (may be NULL)
- `error` TEXT — the error message from the Netlify function

Query the last 50 errors with:

```sql
SELECT created_at, session_id, query, error
FROM error_logs
ORDER BY created_at DESC
LIMIT 50
```

Created by `scripts/setup_error_logs.py`. Rows are written by `logError()` in
`netlify/functions/chat.js` from both the streaming catch and the outer catch —
so repeated identical `error` values usually mean a systemic break (e.g. a
retired Claude model), not a one-off user issue.

## Argument handling

The argument is: $ARGUMENTS

- If blank or empty: default to last 7 days of sessions
- If `today`: filter `started_at >= CURRENT_DATE`
- If `yesterday`: filter `started_at >= CURRENT_DATE - INTERVAL '1 day' AND started_at < CURRENT_DATE`
- If a number (e.g. `14`): filter `started_at >= NOW() - INTERVAL '<n> days'`
- If `search <term>`: query all sessions and filter messages JSONB where user text contains the term (case-insensitive). Also check deflections for the term.
- If `deflections`: only query the deflections table, last 50 entries
- If `errors`: only query the error_logs table, last 50 entries

## Output format

Present results in a readable summary:
- Show session count and date range
- For each session: timestamp, user questions, and short bot responses (truncate to ~200 chars)
- For searches: highlight the matching messages
- For deflections: show the query, nearest match, and score
- For errors: show the timestamp, query, and error message; group repeats and call out any error seen more than once

## Reference

See `scripts/view_chat_logs.py` for the existing Python log viewer.
