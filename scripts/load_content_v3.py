#!/usr/bin/env python3
"""
Load parsed content into database for TomBot v3.

For each section:
- Embeds the answer content (stored in 'embedding')
- Embeds each question variation (stored in 'question_embedding')
- Creates one row per question variation for better matching

This means a section with 10 question variations = 10 rows in the DB,
all pointing to the same answer content but with different question embeddings.
"""

import os
import json
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
import psycopg2

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
NILEDB_URL = os.getenv("NILEDB_URL")


def get_embeddings(texts, model="voyage-3"):
    """Get embeddings from Voyage AI. Handles batching."""
    if not texts:
        return []

    # Voyage allows up to 128 texts per batch
    BATCH_SIZE = 128
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]

        response = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {VOYAGE_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "input": batch,
                "model": model
            }
        )

        if response.status_code == 429:
            # Rate limited - wait and retry
            print("  Rate limited, waiting 5s...")
            time.sleep(5)
            response = requests.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {VOYAGE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "input": batch,
                    "model": model
                }
            )

        if response.status_code != 200:
            print(f"Error from Voyage API: {response.status_code} {response.text}")
            return None

        data = response.json()
        batch_embeddings = [d["embedding"] for d in data["data"]]
        all_embeddings.extend(batch_embeddings)

        # Small delay to avoid rate limits
        if i + BATCH_SIZE < len(texts):
            time.sleep(0.5)

    return all_embeddings


def load_content():
    # Load parsed content
    script_dir = Path(__file__).parent
    parsed_file = script_dir / "parsed_content.json"

    with open(parsed_file, "r", encoding="utf-8") as f:
        sections = json.load(f)

    print(f"Loaded {len(sections)} sections")

    # Connect to database
    conn = psycopg2.connect(NILEDB_URL)
    cur = conn.cursor()

    # Ensure follow_ups column exists (JSONB for array of {text, target} objects)
    cur.execute("""
        ALTER TABLE chunks ADD COLUMN IF NOT EXISTS follow_ups JSONB
    """)
    conn.commit()

    # Clear ALL chunks — ensures no stale data from previous versions
    cur.execute("DELETE FROM chunks")
    deleted = cur.rowcount
    conn.commit()
    print(f"Cleared {deleted} existing rows from chunks table")

    # Collect all texts to embed
    # For each section: the content + all question variations
    content_texts = []
    question_texts = []
    section_indices = []  # Maps question index back to section

    for i, section in enumerate(sections):
        content_texts.append(section["content"])
        for q in section["questions"]:
            question_texts.append(q)
            section_indices.append(i)

    print(f"Embedding {len(content_texts)} content blocks...")
    content_embeddings = get_embeddings(content_texts)
    if not content_embeddings:
        print("Failed to get content embeddings")
        return

    print(f"Embedding {len(question_texts)} questions...")
    question_embeddings = get_embeddings(question_texts)
    if not question_embeddings:
        print("Failed to get question embeddings")
        return

    # Insert rows - one per question variation
    print("Inserting into database...")
    inserted = 0
    q_idx = 0

    for section_idx, section in enumerate(sections):
        content_embedding = content_embeddings[section_idx]

        for question in section["questions"]:
            question_embedding = question_embeddings[q_idx]
            q_idx += 1

            # Generate unique ID: section_id + question hash
            row_id = f"{section['id']}_{q_idx}"

            # Convert follow_ups to JSON string for JSONB column
            follow_ups_json = json.dumps(section.get("follow_ups", []))

            cur.execute("""
                INSERT INTO chunks (
                    id, chunk_type, title, content,
                    embedding, question_text, question_embedding,
                    tags, source_file, follow_ups
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
            """, (
                row_id,
                "content",
                section["id"],  # Use section ID as title
                section["content"],
                content_embedding,
                question,
                question_embedding,
                section.get("drill_downs", []),
                "tombot-content-v3.md",
                follow_ups_json
            ))
            inserted += 1

        # Also insert one row with just the content embedding (no question)
        # This helps with direct content matching
        follow_ups_json = json.dumps(section.get("follow_ups", []))

        cur.execute("""
            INSERT INTO chunks (
                id, chunk_type, title, content,
                embedding, question_text, question_embedding,
                tags, source_file, follow_ups
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
        """, (
            section["id"],  # Main section ID
            "content",
            section["id"],
            section["content"],
            content_embedding,
            None,  # No question text
            None,  # No question embedding
            section.get("drill_downs", []),
            "tombot-content-v3.md",
            follow_ups_json
        ))
        inserted += 1

    conn.commit()
    print(f"Inserted {inserted} rows")

    # === POST-LOAD VALIDATION ===
    print("\n" + "=" * 60)
    print("POST-LOAD VALIDATION")
    print("=" * 60)

    validation_passed = True

    # 1. Row count check
    cur.execute("SELECT COUNT(*) FROM chunks")
    total_db = cur.fetchone()[0]
    if total_db != inserted:
        print(f"FAIL: DB has {total_db} rows but we inserted {inserted}")
        validation_passed = False
    else:
        print(f"OK: Row count matches ({total_db} rows)")

    # 2. All rows should be chunk_type='content' (our type)
    cur.execute("SELECT COUNT(*) FROM chunks WHERE chunk_type != 'content'")
    non_content = cur.fetchone()[0]
    if non_content > 0:
        print(f"FAIL: {non_content} rows have unexpected chunk_type")
        cur.execute("SELECT DISTINCT chunk_type FROM chunks WHERE chunk_type != 'content'")
        types = [r[0] for r in cur.fetchall()]
        print(f"       Found types: {types}")
        validation_passed = False
    else:
        print(f"OK: All rows have chunk_type='content'")

    # 3. Check every section ID from parsed content exists in DB
    expected_ids = set(s["id"] for s in sections)
    cur.execute("SELECT DISTINCT title FROM chunks")
    db_titles = set(r[0] for r in cur.fetchall())

    missing = expected_ids - db_titles
    extra = db_titles - expected_ids
    if missing:
        print(f"FAIL: {len(missing)} sections missing from DB: {sorted(missing)[:10]}")
        validation_passed = False
    else:
        print(f"OK: All {len(expected_ids)} sections present in DB")

    if extra:
        print(f"FAIL: {len(extra)} unexpected sections in DB: {sorted(extra)[:10]}")
        validation_passed = False
    else:
        print(f"OK: No unexpected sections in DB")

    # 4. Check question counts per section match
    cur.execute("""
        SELECT title, COUNT(*) as row_count,
               COUNT(question_embedding) as q_count
        FROM chunks GROUP BY title ORDER BY title
    """)
    db_section_counts = {r[0]: {'rows': r[1], 'questions': r[2]} for r in cur.fetchall()}

    mismatches = []
    for section in sections:
        sid = section["id"]
        expected_rows = len(section["questions"]) + 1  # questions + 1 content-only row
        expected_questions = len(section["questions"])
        actual = db_section_counts.get(sid, {'rows': 0, 'questions': 0})
        if actual['rows'] != expected_rows or actual['questions'] != expected_questions:
            mismatches.append(f"  {sid}: expected {expected_rows} rows ({expected_questions} questions), "
                            f"got {actual['rows']} rows ({actual['questions']} questions)")

    if mismatches:
        print(f"FAIL: {len(mismatches)} sections have wrong row counts:")
        for m in mismatches[:5]:
            print(m)
        validation_passed = False
    else:
        print(f"OK: All section row counts match expected")

    # 5. Summary with question embedding stats
    cur.execute("SELECT COUNT(*) FROM chunks WHERE question_embedding IS NOT NULL")
    q_count = cur.fetchone()[0]
    print(f"\nRows with question embeddings: {q_count}")
    print(f"Content-only rows: {total_db - q_count}")

    # 6. Verify follow_ups are stored correctly
    cur.execute("SELECT COUNT(*) FROM chunks WHERE follow_ups IS NOT NULL AND follow_ups != '[]'::jsonb")
    rows_with_followups = cur.fetchone()[0]
    print(f"Rows with follow-ups: {rows_with_followups}")

    # Check a sample to verify structure
    cur.execute("SELECT title, follow_ups FROM chunks WHERE follow_ups IS NOT NULL LIMIT 1")
    sample = cur.fetchone()
    if sample:
        print(f"Sample follow-ups for {sample[0]}: {len(sample[1])} suggestions")

    # Final verdict
    print("\n" + "=" * 60)
    if validation_passed:
        print("VALIDATION PASSED: DB contents match loaded data exactly")
    else:
        print("VALIDATION FAILED: DB contents do not match loaded data")
        print("Review the errors above and re-run the load script")
    print("=" * 60)

    cur.close()
    conn.close()

    return validation_passed


if __name__ == "__main__":
    import sys
    passed = load_content()
    if not passed:
        sys.exit(1)
