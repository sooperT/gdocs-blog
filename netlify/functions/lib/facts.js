// Screening facts (R1012-22): a job-description line a screener decides yes
// or no (location, work permit, degree, languages, ...) is answered from the
// facts register, never matched to a story. The register is lib/facts.json,
// written by generate_agent_page.py; each fact carries the patterns that mark
// a line as its question. A fact with no value is "not stated".
import DATA from './facts.json' with { type: 'json' };

const compiled = new WeakMap();
function patterns(data) {
  if (!compiled.has(data)) {
    compiled.set(data, (data.facts || []).map(f => ({ fact: f, res: (f.asks || []).map(a => new RegExp(a, 'i')) })));
  }
  return compiled.get(data);
}

// The fact a requirement asks about, or null when it is an experience
// requirement. Long lines are experience that happens to name a place.
export function classifyKnockout(requirement, data = DATA) {
  const text = String(requirement || '').trim();
  if (!text || text.length > (data.max_ask_chars || 160)) return null;
  for (const { fact, res } of patterns(data)) {
    if (res.some(re => re.test(text))) return fact;
  }
  return null;
}

// What the fact says to this requirement: its core, plus only the qualifiers
// the requirement asks about (a Hørsholm office line does not get "remote
// roles across the EU"). Null when Tom has not stated the fact.
export function answerFor(requirement, fact) {
  if (!fact || typeof fact.base !== 'string' || !fact.base) return null;
  const text = String(requirement || '');
  const extra = (fact.qualifiers || []).filter(q => new RegExp(q.ask, 'i').test(text)).map(q => q.text);
  return [fact.base, ...extra].join('; ');
}

export const FACT_NOTE = 'A fact from Tom\'s record, not a verdict: compare it with the requirement yourself.';
export const NOT_STATED_NOTE = 'Tom has not stated this. If it matters for the role, ask him (see contact); if it is minor, leave it out.';
