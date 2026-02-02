#!/usr/bin/env python3
"""View TomBot chat logs from the database."""

import os
import json
import argparse
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def view_chat_logs(limit=None, show_full=False):
    conn = psycopg2.connect(os.environ['NILEDB_URL'])
    cur = conn.cursor()

    # Get all chat sessions, most recent first
    cur.execute('''
        SELECT session_id, started_at, updated_at, messages, retrieval_log
        FROM chat_logs
        ORDER BY started_at DESC
    ''')

    rows = cur.fetchall()

    if not rows:
        print("No chat logs found.")
        return

    # Filter to sessions with actual conversations (more than 1 exchange or non-test)
    real_sessions = []
    for row in rows:
        session_id, started_at, updated_at, messages, retrieval_log = row
        if messages and len(messages) > 0:
            # Check if it's not just a test
            first_user_msg = messages[0].get('user', '').lower() if messages else ''
            if first_user_msg not in ['test', 'hello', 'hi']:
                real_sessions.append(row)
            elif len(messages) > 1:
                real_sessions.append(row)

    print(f"Found {len(rows)} total sessions, {len(real_sessions)} with substantive conversations\n")

    # Summary stats
    total_exchanges = sum(len(row[3]) if row[3] else 0 for row in rows)
    print(f"Total exchanges: {total_exchanges}")

    # Date range
    if rows:
        earliest = rows[-1][1]
        latest = rows[0][1]
        print(f"Date range: {earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}")

    print("\n" + "=" * 80)
    print("RECENT CONVERSATIONS")
    print("=" * 80)

    sessions_to_show = real_sessions[:limit] if limit else real_sessions

    for row in sessions_to_show:
        session_id, started_at, updated_at, messages, retrieval_log = row

        print(f"\n[{started_at.strftime('%Y-%m-%d %H:%M')}] Session: {session_id[:20]}...")
        print("-" * 60)

        if messages:
            for i, msg in enumerate(messages):
                user_msg = msg.get('user', '')
                assistant_msg = msg.get('assistant', '')

                if user_msg:
                    print(f"\nUSER: {user_msg}")
                if assistant_msg:
                    if show_full:
                        print(f"BOT:  {assistant_msg}")
                    else:
                        # Truncate long responses
                        if len(assistant_msg) > 300:
                            assistant_msg = assistant_msg[:300] + "..."
                        print(f"BOT:  {assistant_msg}")

                # Show retrieval info
                if retrieval_log and i < len(retrieval_log):
                    ret = retrieval_log[i]
                    matches = ret.get('matches', [])
                    method = ret.get('method', 'unknown')
                    if matches and isinstance(matches, list):
                        match_parts = []
                        for m in matches:
                            if isinstance(m, dict):
                                match_parts.append(f"{m.get('section', '?')} ({m.get('score', '?')})")
                        if match_parts:
                            print(f"      -> [{method}] {', '.join(match_parts)}")
                    elif method == 'none':
                        print(f"      -> [DEFLECTED]")

        print()

    # Deflections
    print("\n" + "=" * 80)
    print("RECENT DEFLECTIONS (queries that didn't match)")
    print("=" * 80)

    try:
        cur.execute('''
            SELECT query, top_match, top_score, created_at
            FROM deflections
            ORDER BY created_at DESC
            LIMIT 30
        ''')
        deflections = cur.fetchall()

        if deflections:
            for d in deflections:
                query, top_match, top_score, created_at = d
                score_str = f"{top_score:.3f}" if top_score else "N/A"
                print(f"\n[{created_at.strftime('%Y-%m-%d %H:%M')}] \"{query}\"")
                print(f"    Nearest match: {top_match or 'None'} (score: {score_str})")
        else:
            print("No deflections logged.")
    except Exception as e:
        print(f"Could not fetch deflections: {e}")

    # User questions summary
    print("\n" + "=" * 80)
    print("ALL USER QUESTIONS")
    print("=" * 80)

    all_questions = []
    for row in rows:
        messages = row[3]
        if messages:
            for msg in messages:
                q = msg.get('user', '')
                if q:
                    all_questions.append(q)

    print(f"\nTotal questions asked: {len(all_questions)}")
    print("\nFull list:")
    for i, q in enumerate(all_questions, 1):
        print(f"  {i}. {q}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='View TomBot chat logs')
    parser.add_argument('-n', '--limit', type=int, default=20, help='Number of sessions to show')
    parser.add_argument('-f', '--full', action='store_true', help='Show full responses')
    args = parser.parse_args()

    view_chat_logs(limit=args.limit, show_full=args.full)
