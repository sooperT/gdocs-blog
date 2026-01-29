#!/usr/bin/env python3
"""Load TomBot CV content into the RAG database.

Content sources (per cv-chatbot-prd-v2.md):
- cv-chatbot-career-content-mega-v3.md: roles, competencies, themes, basic info
- cv-chatbot-key-stories-v2.md: STAR narratives
- tricky-questions-final.md: sensitive Q&A with careful framing

Target: 67 chunks total
- 16 roles (role_R01 to role_R16)
- 14 stories (story_S01 to story_S14)
- 19 tricky questions (tq_TQ01 to tq_TQ19)
- 6 competencies (comp_C01 to comp_C06)
- 5 themes (theme_TH01 to theme_TH05)
- 7 basic info (info_BI01 to info_BI07)
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
import requests

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
NILEDB_URL = os.getenv("NILEDB_URL")
CONTENT_DIR = Path(__file__).parent.parent / "docs" / "tombot" / "RAG"


def get_embeddings(texts: list[str], max_retries: int = 5) -> list[list[float]]:
    """Get embeddings from Voyage AI (voyage-3, 1024 dims)."""
    import time

    for attempt in range(max_retries):
        response = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {VOYAGE_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "input": texts,
                "model": "voyage-3"
            }
        )

        if response.status_code == 429:
            wait_time = 30 + (attempt * 30)  # 30, 60, 90, 120, 150 seconds
            print(f"      Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
            continue

        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    raise Exception("Max retries exceeded for embeddings API")


# Company data for denormalisation
COMPANIES = {
    "Novo Nordisk": {"years": (2020, 2024), "location": "Copenhagen"},
    "LEO Innovation Lab": {"years": (2016, 2020), "location": "Copenhagen"},
    "TwentyThree": {"years": (2016, 2016), "location": "Copenhagen"},
    "Opbeat": {"years": (2014, 2016), "location": "Copenhagen"},
    "EuroDNS": {"years": (2013, 2014), "location": "Luxembourg/Copenhagen"},
    "Independent Consultant": {"years": (2010, 2013), "location": "Copenhagen"},
    "UK2 Group": {"years": (2008, 2010), "location": "London"},
    "Host Europe Group": {"years": (2003, 2008), "location": "UK"},
    "TextualHealing": {"years": (2002, 2004), "location": "UK"},
    "Freelance": {"years": (2001, 2004), "location": "UK"},
}

# Role to company mapping
ROLE_COMPANIES = {
    "R16": "Novo Nordisk", "R15": "Novo Nordisk",
    "R14": "LEO Innovation Lab", "R13": "LEO Innovation Lab", "R12": "LEO Innovation Lab",
    "R11": "TwentyThree",
    "R10": "Opbeat",
    "R09": "EuroDNS",
    "R08": "Independent Consultant",
    "R07": "UK2 Group",
    "R06": "Host Europe Group", "R05": "Host Europe Group",
    "R04": "Host Europe Group", "R03": "Host Europe Group",
    "R02": "TextualHealing",
    "R01": "Freelance",
}

# Role years
ROLE_YEARS = {
    "R16": (2022, 2024), "R15": (2020, 2022),
    "R14": (2018, 2020), "R13": (2018, 2018), "R12": (2016, 2017),
    "R11": (2016, 2016),
    "R10": (2014, 2016),
    "R09": (2013, 2014),
    "R08": (2010, 2013),
    "R07": (2008, 2010),
    "R06": (2006, 2008), "R05": (2005, 2006), "R04": (2004, 2005), "R03": (2003, 2004),
    "R02": (2002, 2004),
    "R01": (2001, 2004),
}

# Role titles
ROLE_TITLES = {
    "R16": "Associate Product Director",
    "R15": "Product Manager (Wegovycare)",
    "R14": "PM/GM - Diagnosis App",
    "R13": "PM/GM - Skincoach",
    "R12": "PM/GM - TREAT",
    "R11": "Head of Marketing (contract)",
    "R10": "Head of Marketing",
    "R09": "Marketing Director",
    "R08": "Independent Consultant",
    "R07": "Head of Group Strategy",
    "R06": "Head of New Media",
    "R05": "Group Design Manager",
    "R04": "Web Designer",
    "R03": "Sales Executive",
    "R02": "Co-founder / Web Director",
    "R01": "Freelance Web Designer",
}


def parse_roles(content: str) -> list[dict]:
    """Parse roles from career content markdown."""
    chunks = []

    # Find role sections like ### [R16] Associate Product Director
    role_pattern = r'### \[(R\d+)\] ([^\n]+)\n(.*?)(?=### \[R|## [A-Z]|# SECTION|$)'
    matches = re.findall(role_pattern, content, re.DOTALL)

    for role_id, title, body in matches:
        company = ROLE_COMPANIES.get(role_id, "Unknown")
        years = ROLE_YEARS.get(role_id, (None, None))

        # Clean up the body - extract key info
        body = body.strip()

        # Build self-contained chunk content
        chunk_content = f"{title} at {company} ({years[0]}-{years[1]})\n\n{body}"

        # Extract tags from role-level tags line
        tags = []
        tags_match = re.search(r'\*\*Role-level tags:\*\* `([^`]+)`', body)
        if tags_match:
            tags = [t.strip() for t in tags_match.group(1).replace('`', '').split()]

        chunks.append({
            "id": f"role_{role_id}",
            "chunk_type": "role",
            "title": f"{title} at {company} ({years[0]}-{years[1]})",
            "content": chunk_content,
            "company_name": company,
            "role_title": title,
            "years_start": years[0],
            "years_end": years[1],
            "tags": tags,
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    return chunks


def parse_stories(content: str) -> list[dict]:
    """Parse stories from key stories markdown."""
    chunks = []

    # Stories start with ## Title and have Role: Rxx
    story_pattern = r'## ([^\n]+)\n\n\*\*Role:\*\* (R\d+[^*]*)\n\*\*Tags:\*\* ([^\n]+)\n\*\*Good for[^:]*:\*\* ([^\n]+)\n(.*?)(?=\n## |\n# |$)'
    matches = re.findall(story_pattern, content, re.DOTALL)

    story_num = 1
    for title, role_ref, tags_str, good_for, body in matches:
        # Extract role ID
        role_match = re.search(r'R(\d+)', role_ref)
        role_id = f"R{role_match.group(1)}" if role_match else None

        company = ROLE_COMPANIES.get(role_id) if role_id else None
        years = ROLE_YEARS.get(role_id, (None, None)) if role_id else (None, None)

        # Parse tags
        tags = [t.strip().strip('`') for t in tags_str.split('`') if t.strip()]

        # Parse good_for patterns
        good_for_list = [g.strip().strip('"') for g in good_for.split('/')]

        # Build self-contained content with context baked in
        context = ""
        if company and years[0]:
            context = f"At {company} ({years[0]}-{years[1]}), "

        chunk_content = f"{title}\n\n{context}{body.strip()}"

        chunks.append({
            "id": f"story_S{str(story_num).zfill(2)}",
            "chunk_type": "story",
            "title": title,
            "content": chunk_content,
            "company_name": company,
            "role_title": ROLE_TITLES.get(role_id) if role_id else None,
            "years_start": years[0],
            "years_end": years[1],
            "good_for": good_for_list,
            "tags": tags,
            "source_file": "cv-chatbot-key-stories-v2.md"
        })
        story_num += 1

    # Also parse the career arc (special story)
    career_arc_match = re.search(r'# THE CAREER ARC\n\n\*\*Good for[^:]*:\*\* ([^\n]+)\n\n---\n\n(.*?)(?=\n# INDIVIDUAL|\n---\n\n#)', content, re.DOTALL)
    if career_arc_match:
        good_for = career_arc_match.group(1)
        body = career_arc_match.group(2)
        chunks.insert(0, {
            "id": "story_S01",
            "chunk_type": "story",
            "title": "Career Arc",
            "content": f"Career Arc: Walk me through your career\n\n{body.strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": 2001,
            "years_end": 2024,
            "good_for": [g.strip().strip('"') for g in good_for.split('/')],
            "tags": ["career-arc", "overview"],
            "source_file": "cv-chatbot-key-stories-v2.md"
        })
        # Renumber other stories
        for i, chunk in enumerate(chunks[1:], start=2):
            if chunk["chunk_type"] == "story":
                chunk["id"] = f"story_S{str(i).zfill(2)}"

    return chunks


def parse_tricky_questions(content: str) -> list[dict]:
    """Parse tricky questions from markdown."""
    chunks = []

    # Pattern for questions: ## Question text followed by answer
    # Handle both simple Q&A and compound questions with sub-stories
    sections = re.split(r'\n## ', content)

    tq_num = 1
    for section in sections[1:]:  # Skip header
        if section.startswith('#') or not section.strip():
            continue

        lines = section.strip().split('\n')
        question = lines[0].strip()

        # Skip section headers like "1. CURRENT SITUATION"
        if re.match(r'^\d+\.\s+[A-Z]', question):
            continue

        # Get the answer (everything after the question)
        answer = '\n'.join(lines[1:]).strip()

        # Skip empty answers or meta-sections
        if not answer or question.startswith('Off-topic') or question.startswith('Boundaries'):
            continue

        # Skip document meta like "Purpose"
        if question == 'Purpose':
            continue

        # Determine if role-specific
        role_match = re.search(r'\[(R\d+)\]', answer)
        role_id = role_match.group(1) if role_match else None
        company = ROLE_COMPANIES.get(role_id) if role_id else None
        years = ROLE_YEARS.get(role_id, (None, None)) if role_id else (None, None)

        # Build chunk
        chunk_content = f"Question: {question}\n\nAnswer: {answer}"

        chunks.append({
            "id": f"tq_TQ{str(tq_num).zfill(2)}",
            "chunk_type": "tricky_question",
            "title": question,
            "content": chunk_content,
            "question_text": question,
            "company_name": company,
            "role_title": ROLE_TITLES.get(role_id) if role_id else None,
            "years_start": years[0],
            "years_end": years[1],
            "tags": [],
            "source_file": "tricky-questions-final.md"
        })
        tq_num += 1

    return chunks


def parse_competencies(content: str) -> list[dict]:
    """Parse competency variants from career content."""
    chunks = []

    # Find competency sections
    comp_pattern = r'## Competency Set: ([^\n]+)\n\n(.*?)(?=\n## |\n---|\n# SECTION)'
    matches = re.findall(comp_pattern, content, re.DOTALL)

    variants = {
        "General Product": "C01",
        "Enablement / Product Ops": "C02",
        "Growth / Consumer": "C03",
    }

    for name, body in matches:
        comp_id = variants.get(name, f"C0{len(chunks)+1}")

        chunks.append({
            "id": f"comp_{comp_id}",
            "chunk_type": "competency",
            "title": f"Summary - {name}",
            "content": f"Competency Profile: {name}\n\n{body.strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["competency", name.lower().replace(' ', '-').replace('/', '-')],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    # Also parse summary statement variants from Section F
    summary_pattern = r'## (General|Growth|Enablement|Hands-on|Developer|Transformation)[^\n]*\n([^#]+?)(?=\n## |\n---|\n# )'
    summary_matches = re.findall(summary_pattern, content, re.DOTALL)

    variant_ids = {
        "General": "C01", "Growth": "C03", "Enablement": "C02",
        "Hands-on": "C04", "Developer": "C05", "Transformation": "C06"
    }

    for variant, body in summary_matches:
        comp_id = variant_ids.get(variant)
        if comp_id and not any(c["id"] == f"comp_{comp_id}" for c in chunks):
            chunks.append({
                "id": f"comp_{comp_id}",
                "chunk_type": "competency",
                "title": f"Summary - {variant}",
                "content": f"Professional Summary ({variant}):\n\n{body.strip()}",
                "company_name": None,
                "role_title": None,
                "years_start": None,
                "years_end": None,
                "tags": ["summary", variant.lower()],
                "source_file": "cv-chatbot-career-content-mega-v3.md"
            })

    return chunks


def parse_themes(content: str) -> list[dict]:
    """Parse career themes from career content."""
    chunks = []

    # Find theme sections in SECTION D
    theme_section = re.search(r'# SECTION D: KEY THEMES\n\n(.*?)(?=\n# SECTION E)', content, re.DOTALL)
    if not theme_section:
        return chunks

    theme_content = theme_section.group(1)

    # Parse individual themes
    theme_pattern = r'## ([^\n]+)\n([^#]+?)(?=\n## |\n---|\n# |$)'
    matches = re.findall(theme_pattern, theme_content, re.DOTALL)

    theme_ids = {
        "Turnaround specialist": "TH01",
        "Growth & conversion": "TH02",
        "Building from scratch": "TH03",
        "Bridging technical and commercial": "TH04",
        "International experience": "TH05",
    }

    for name, body in matches:
        theme_id = theme_ids.get(name, f"TH0{len(chunks)+1}")

        chunks.append({
            "id": f"theme_{theme_id}",
            "chunk_type": "theme",
            "title": name,
            "content": f"{name}\n\n{body.strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["theme", name.lower().replace(' ', '-').replace('&', 'and')],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    return chunks


def parse_basic_info(content: str) -> list[dict]:
    """Parse basic info from career content."""
    chunks = []

    # Contact info
    contact_match = re.search(r'## Basic Information\n\n(.*?)(?=\n## Private|\n## Education)', content, re.DOTALL)
    if contact_match:
        chunks.append({
            "id": "info_BI01",
            "chunk_type": "basic_info",
            "title": "Contact Information",
            "content": f"Contact Information\n\n{contact_match.group(1).strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["contact"],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    # Education
    edu_match = re.search(r'## Education\n\n(.*?)(?=\n## Certificates|\n## Languages)', content, re.DOTALL)
    if edu_match:
        chunks.append({
            "id": "info_BI02",
            "chunk_type": "basic_info",
            "title": "Education",
            "content": f"Education\n\n{edu_match.group(1).strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["education"],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    # Certificates
    cert_match = re.search(r'## Certificates\n\n(.*?)(?=\n## Languages)', content, re.DOTALL)
    if cert_match:
        chunks.append({
            "id": "info_BI03",
            "chunk_type": "basic_info",
            "title": "Certificates",
            "content": f"Certificates\n\n{cert_match.group(1).strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["certificates"],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    # Languages
    lang_match = re.search(r'## Languages\n\n(.*?)(?=\n## Interests)', content, re.DOTALL)
    if lang_match:
        chunks.append({
            "id": "info_BI04",
            "chunk_type": "basic_info",
            "title": "Languages",
            "content": f"Languages\n\n{lang_match.group(1).strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["languages"],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    # Interests
    interests_match = re.search(r'## Interests\n\n(.*?)(?=\n---|\n# SECTION)', content, re.DOTALL)
    if interests_match:
        chunks.append({
            "id": "info_BI05",
            "chunk_type": "basic_info",
            "title": "Interests",
            "content": f"Interests\n\n{interests_match.group(1).strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["interests"],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    # Tools
    tools_match = re.search(r'## Tools\n\n(.*?)(?=\n## Tech Stack)', content, re.DOTALL)
    if tools_match:
        chunks.append({
            "id": "info_BI06",
            "chunk_type": "basic_info",
            "title": "Tools",
            "content": f"Tools\n\n{tools_match.group(1).strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["tools"],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    # Tech Stack
    tech_match = re.search(r'## Tech Stack\n\n(.*?)(?=\n---|\n# SECTION)', content, re.DOTALL)
    if tech_match:
        chunks.append({
            "id": "info_BI07",
            "chunk_type": "basic_info",
            "title": "Tech Stack",
            "content": f"Tech Stack\n\n{tech_match.group(1).strip()}",
            "company_name": None,
            "role_title": None,
            "years_start": None,
            "years_end": None,
            "tags": ["tech-stack"],
            "source_file": "cv-chatbot-career-content-mega-v3.md"
        })

    return chunks


def load_aliases(conn):
    """Load company and product aliases."""
    cur = conn.cursor()

    aliases = [
        # Company aliases
        ("Novo", "Novo Nordisk", "company"),
        ("NN", "Novo Nordisk", "company"),
        ("LEO", "LEO Innovation Lab", "company"),
        ("iLab", "LEO Innovation Lab", "company"),
        ("Innovation Lab", "LEO Innovation Lab", "company"),
        ("123-reg", "Host Europe Group", "company"),
        ("Pipex", "Host Europe Group", "company"),
        ("Host Europe", "Host Europe Group", "company"),
        ("UK2", "UK2 Group", "company"),
        # Product aliases
        ("TREAT", "TREAT app", "product"),
        ("Skincoach", "Skincoach app", "product"),
        # Person aliases
        ("Tom", "Tom Stenson", "person"),
        ("Stenson", "Tom Stenson", "person"),
    ]

    for alias, canonical, alias_type in aliases:
        cur.execute("""
            INSERT INTO aliases (alias, canonical_name, alias_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (alias) DO UPDATE SET canonical_name = EXCLUDED.canonical_name
        """, (alias, canonical, alias_type))

    conn.commit()
    print(f"   Loaded {len(aliases)} aliases")


def main():
    print("Loading TomBot RAG content...")
    print(f"   Content directory: {CONTENT_DIR}")

    # Read source files
    career_content = (CONTENT_DIR / "cv-chatbot-career-content-mega-v3.md").read_text()
    stories_content = (CONTENT_DIR / "cv-chatbot-key-stories-v2.md").read_text()
    tricky_content = (CONTENT_DIR / "tricky-questions-final.md").read_text()

    # Parse all content types
    print("\nParsing content...")

    roles = parse_roles(career_content)
    print(f"   Roles: {len(roles)}")

    stories = parse_stories(stories_content)
    print(f"   Stories: {len(stories)}")

    tricky_questions = parse_tricky_questions(tricky_content)
    print(f"   Tricky questions: {len(tricky_questions)}")

    competencies = parse_competencies(career_content)
    print(f"   Competencies: {len(competencies)}")

    themes = parse_themes(career_content)
    print(f"   Themes: {len(themes)}")

    basic_info = parse_basic_info(career_content)
    print(f"   Basic info: {len(basic_info)}")

    all_chunks = roles + stories + tricky_questions + competencies + themes + basic_info
    print(f"\n   Total chunks: {len(all_chunks)}")

    # Connect to database
    conn = psycopg2.connect(NILEDB_URL)
    cur = conn.cursor()

    # Clear existing data
    cur.execute("TRUNCATE chunks, aliases;")
    conn.commit()
    print("\n   Cleared existing data")

    # Generate embeddings and insert chunks
    print("\nGenerating embeddings and inserting chunks...")
    import time
    batch_size = 10  # Smaller batches to avoid rate limits
    time.sleep(60)  # Wait for rate limit to reset

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]

        # Get content embeddings
        texts = [c["content"] for c in batch]
        embeddings = get_embeddings(texts)

        # For tricky questions, also embed the question text
        question_texts = []
        question_indices = []
        for j, chunk in enumerate(batch):
            if chunk.get("question_text"):
                question_texts.append(chunk["question_text"])
                question_indices.append(j)

        question_embeddings = get_embeddings(question_texts) if question_texts else []

        # Insert each chunk
        for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
            # Get question embedding if applicable
            q_embedding = None
            if j in question_indices:
                q_idx = question_indices.index(j)
                q_embedding = question_embeddings[q_idx]

            cur.execute("""
                INSERT INTO chunks (
                    id, chunk_type, title, content, embedding,
                    company_name, role_title, years_start, years_end,
                    question_text, question_embedding, good_for, tags, source_file
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """, (
                chunk["id"],
                chunk["chunk_type"],
                chunk.get("title"),
                chunk["content"],
                embedding,
                chunk.get("company_name"),
                chunk.get("role_title"),
                chunk.get("years_start"),
                chunk.get("years_end"),
                chunk.get("question_text"),
                q_embedding,
                chunk.get("good_for"),
                chunk.get("tags"),
                chunk.get("source_file")
            ))

        conn.commit()
        print(f"   Inserted batch {i//batch_size + 1}/{(len(all_chunks)-1)//batch_size + 1}")
        time.sleep(5)  # Delay between batches to avoid rate limits

    # Load aliases
    print("\nLoading aliases...")
    load_aliases(conn)

    # Summary
    cur.execute("SELECT chunk_type, COUNT(*) FROM chunks GROUP BY chunk_type ORDER BY chunk_type")
    counts = cur.fetchall()
    print("\nChunk counts by type:")
    for chunk_type, count in counts:
        print(f"   {chunk_type}: {count}")

    cur.execute("SELECT COUNT(*) FROM chunks")
    total = cur.fetchone()[0]
    print(f"\n   Total: {total} chunks loaded")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
