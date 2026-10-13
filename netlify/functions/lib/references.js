// References per period (R1012-15): LinkedIn recommendations vouch for a
// role, never for a claim. A row's section id maps by prefix to the period
// it belongs to; the count and URL come from lib/references.json, written by
// generate_agent_page.py from the LinkedIn export. Unknown prefix -> null.
import DATA from './references.json' with { type: 'json' };

export function referencesFor(sectionId, data = DATA) {
  if (typeof sectionId !== 'string') return null;
  const prefix = sectionId.split('.')[0];
  const key = Object.prototype.hasOwnProperty.call(data.prefixes || {}, prefix) ? data.prefixes[prefix] : null;
  const p = key && Object.prototype.hasOwnProperty.call(data.periods || {}, key) ? data.periods[key] : null;
  if (!p) return null;
  return { period: p.label, count: p.count, url: p.url, tier: 'attested', note: 'References for the role, not for this claim.' };
}
