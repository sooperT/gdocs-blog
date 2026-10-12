#!/usr/bin/env python3
"""
Parse tombot-content-v3.md into structured chunks for RAG.

Output format for each section:
{
    "id": "NOVO.R1",
    "questions": ["Tell me about...", "What did you do..."],
    "content": "The answer content...",
    "drill_downs": ["NOVO.R1.TRANSFORM", "NOVO.R1.ALGORITHM"],
    "follow_ups": [
        {"text": "tell me about X", "target": "SECTION.ID"},
        ...
    ],
    "attested": [
        {"name": "First Last", "title": "current title", "company": "Company",
         "date": "YYYY-MM-DD", "excerpt": "verbatim excerpt"},
        ...
    ],
    "direct_answers": ["one direct answer", ...],
    "external": [{"url": "https://...", "label": "label"}, ...]
}

Agent-side blocks (PRD W1b, D2; ruling N1010-6 a) are lifted out of
`content`, the same way Questions and follow-ups are, so TomBot chat never
sees them. They reach agent surfaces only (/ask, /for-agents/):

    **Attested:**
    - First Last (current title, Company; YYYY-MM-DD): "verbatim excerpt" [linkedin]

    **Direct answers:**
    - one direct answer
      (indented continuation lines belong to the item above)

    **External:**
    - [label](https://url)
"""

import re
import json
from pathlib import Path

def parse_content_doc(filepath: str):
    """Parse the content document into structured chunks."""

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by ## headers (section IDs)
    # Match ## followed by ID pattern (letters, dots, numbers)
    section_pattern = r'^## ([A-Z][A-Z0-9_.]+)\s*$'

    sections = []
    lines = content.split('\n')

    current_section = None
    current_lines = []

    for line in lines:
        match = re.match(section_pattern, line)
        if match:
            # Save previous section if exists
            if current_section:
                sections.append({
                    'id': current_section,
                    'raw': '\n'.join(current_lines)
                })
            # Start new section
            current_section = match.group(1)
            current_lines = []
        elif current_section:
            current_lines.append(line)

    # Don't forget the last section
    if current_section:
        sections.append({
            'id': current_section,
            'raw': '\n'.join(current_lines)
        })

    # Parse each section
    parsed = []
    for section in sections:
        parsed_section = parse_section(section['id'], section['raw'])
        if parsed_section:
            parsed.append(parsed_section)

    return parsed


# A labelled agent-side block: the bold label, then list items ("- ...") and
# indented continuation lines, up to the first line that is neither.
def _block_pattern(label):
    return re.compile(
        r'\*\*' + re.escape(label) + r':\*\*[ \t]*\n((?:[ \t]*- .*\n?|[ \t]+\S.*\n?)+)'
    )


ATTESTED_BLOCK = _block_pattern('Attested')
DIRECT_ANSWERS_BLOCK = _block_pattern('Direct answers')
EXTERNAL_BLOCK = _block_pattern('External')

# - First Last (current title, Company; YYYY-MM-DD): "excerpt" [linkedin]
# The title may hold commas and parentheses; the company is after the last ", ".
ATTESTED_LINE = re.compile(
    r'^- (?P<name>[^(]+?) \((?P<inner>.+); (?P<date>\d{4}-\d{2}-\d{2})\): '
    r'"(?P<excerpt>.+)" \[linkedin\]$'
)
EXTERNAL_LINE = re.compile(r'^- \[(?P<label>[^\]]+)\]\((?P<url>https?://[^)\s]+)\)')


def _block_items(block):
    """Top-level '- ' items of a block, each with its indented continuation lines."""
    items = []
    for line in block.split('\n'):
        if not line.strip():
            continue
        if line.startswith('- '):
            items.append(line.rstrip())
        elif items:
            items[-1] += '\n' + line.strip()
    return items


def parse_attested(block, section_id):
    entries = []
    for item in _block_items(block):
        m = ATTESTED_LINE.match(item)
        if not m:
            raise ValueError(f'{section_id}: Attested line not in the expected shape: {item!r}')
        title, _, company = m.group('inner').rpartition(', ')
        if not title:
            raise ValueError(f'{section_id}: Attested line has no "title, company": {item!r}')
        entries.append({
            'name': m.group('name').strip(),
            'title': title.strip(),
            'company': company.strip(),
            'date': m.group('date'),
            'excerpt': m.group('excerpt'),
        })
    return entries


def parse_external(block, section_id):
    entries = []
    for item in _block_items(block):
        m = EXTERNAL_LINE.match(item)
        if not m:
            raise ValueError(f'{section_id}: External line not in the expected shape: {item!r}')
        entries.append({'url': m.group('url'), 'label': m.group('label').strip()})
    return entries


def parse_section(section_id: str, raw: str):
    """Parse a single section into structured format."""

    # Extract questions
    questions = []
    questions_match = re.search(
        r'\*\*Questions that route here:\*\*\s*\n((?:- .+\n?)+)',
        raw
    )
    if questions_match:
        questions_block = questions_match.group(1)
        questions = [
            line.strip()[2:].strip()  # Remove "- " prefix
            for line in questions_block.strip().split('\n')
            if line.strip().startswith('- ')
        ]

    # Extract drill-downs from comments
    drill_downs = []
    drilldown_match = re.search(r'<!-- DRILL-DOWNS: ([^>]+) -->', raw)
    if drilldown_match:
        drill_downs = [
            d.strip()
            for d in drilldown_match.group(1).split(',')
            if d.strip()
        ]

    # Extract follow-up suggestions
    follow_ups = []
    followups_match = re.search(
        r'\*\*Suggested follow-ups:\*\*\s*\n((?:- .+\n?)+)',
        raw
    )
    if followups_match:
        followups_block = followups_match.group(1)
        for line in followups_block.strip().split('\n'):
            if line.strip().startswith('- '):
                # Parse: - "suggestion text" [TARGET.ID]
                fu_match = re.match(r'- "([^"]+)"\s*\[([A-Z][A-Z0-9_.]+)\]', line.strip())
                if fu_match:
                    follow_ups.append({
                        'text': fu_match.group(1),
                        'target': fu_match.group(2)
                    })
                else:
                    # Fallback: just the text without target (shouldn't happen but handle gracefully)
                    text_match = re.match(r'- "([^"]+)"', line.strip())
                    if text_match:
                        follow_ups.append({
                            'text': text_match.group(1),
                            'target': None
                        })

    # Agent-side blocks: parsed into their own fields, stripped from content
    attested_match = ATTESTED_BLOCK.search(raw)
    attested = parse_attested(attested_match.group(1), section_id) if attested_match else []
    direct_match = DIRECT_ANSWERS_BLOCK.search(raw)
    direct_answers = [i[2:].strip() for i in _block_items(direct_match.group(1))] if direct_match else []
    external_match = EXTERNAL_BLOCK.search(raw)
    external = parse_external(external_match.group(1), section_id) if external_match else []

    # Extract content (everything after questions block and comments, before ---)
    # Remove the questions block and follow-ups block
    content = raw
    if questions_match:
        content = content.replace(questions_match.group(0), '')
    if followups_match:
        content = content.replace(followups_match.group(0), '')
        # Also remove the header line
        content = content.replace('**Suggested follow-ups:**', '')
    # Each block goes with the blank line after it, so the prose around it is
    # exactly what it was before the block was added.
    for block_match in (attested_match, direct_match, external_match):
        if block_match:
            content = re.sub(re.escape(block_match.group(0)) + r'\n?', '', content, count=1)

    # Remove HTML comments
    content = re.sub(r'<!--[^>]*-->\n?', '', content)

    # Remove leading/trailing whitespace and separators
    content = content.strip()
    if content.endswith('---'):
        content = content[:-3].strip()

    # Skip if no content
    if not content or content == '':
        return None

    return {
        'id': section_id,
        'questions': questions,
        'content': content,
        'drill_downs': drill_downs,
        'follow_ups': follow_ups,
        'attested': attested,
        'direct_answers': direct_answers,
        'external': external,
    }


def main():
    # Find content file
    script_dir = Path(__file__).parent
    content_file = script_dir.parent / 'docs' / 'tombot' / 'tombot-content-v3.md'

    if not content_file.exists():
        print(f"Content file not found: {content_file}")
        return

    # Parse
    chunks = parse_content_doc(str(content_file))

    # Output stats
    print(f"Parsed {len(chunks)} sections")

    total_questions = sum(len(c['questions']) for c in chunks)
    print(f"Total questions: {total_questions}")

    sections_with_drilldowns = sum(1 for c in chunks if c['drill_downs'])
    print(f"Sections with drill-downs: {sections_with_drilldowns}")

    total_followups = sum(len(c['follow_ups']) for c in chunks)
    sections_with_followups = sum(1 for c in chunks if c['follow_ups'])
    followups_with_targets = sum(
        1 for c in chunks for f in c['follow_ups'] if f['target']
    )
    print(f"Total follow-ups: {total_followups} ({sections_with_followups} sections)")
    print(f"Follow-ups with targets: {followups_with_targets}")
    for field in ('attested', 'direct_answers', 'external'):
        n = sum(len(c[field]) for c in chunks)
        print(f"{field}: {n} entries ({sum(1 for c in chunks if c[field])} sections)")

    # Show sample
    print("\n--- Sample (first 3 sections) ---\n")
    for chunk in chunks[:3]:
        print(f"ID: {chunk['id']}")
        print(f"Questions ({len(chunk['questions'])}): {chunk['questions'][:3]}...")
        print(f"Content preview: {chunk['content'][:100]}...")
        print(f"Drill-downs: {chunk['drill_downs']}")
        print(f"Follow-ups: {chunk['follow_ups']}")
        print()

    # Save to JSON
    output_file = script_dir / 'parsed_content.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {output_file}")


if __name__ == '__main__':
    main()
