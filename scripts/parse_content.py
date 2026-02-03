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
    ]
}
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

    # Extract content (everything after questions block and comments, before ---)
    # Remove the questions block and follow-ups block
    content = raw
    if questions_match:
        content = content.replace(questions_match.group(0), '')
    if followups_match:
        content = content.replace(followups_match.group(0), '')
        # Also remove the header line
        content = content.replace('**Suggested follow-ups:**', '')

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
        'follow_ups': follow_ups
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
