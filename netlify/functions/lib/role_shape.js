// Role shape of a brief (PRD W4.3, guardrail 8, backlog item 27).
// Three labels from fixed lists, never free text, so the calibrate log can
// say what kind of roles are being matched (J7) without ever logging the
// brief. Unknown is a label too. First match in list order wins; the lists
// are ordered so the more specific word is tried first.

export const SENIORITY = ['head', 'director', 'vp', 'principal', 'lead', 'senior', 'manager', 'associate', 'unknown'];
export const FUNCTION = ['product', 'growth', 'engineering', 'design', 'data', 'marketing', 'operations', 'strategy', 'unknown'];
export const SECTOR = ['health', 'fintech', 'saas', 'hosting', 'ecommerce', 'ai', 'pharma', 'consulting', 'unknown'];

// label -> regex, applied to the lowercased brief. Patterns are explicit so
// a label never comes from a word the list does not contain.
const RULES = {
  seniority: [
    ['head', /\bhead of\b/],
    ['director', /\bdirector\b/],
    ['vp', /\b(vp|vice president)\b/],
    ['principal', /\bprincipal\b/],
    ['lead', /\b(lead|leader)\b/],
    ['senior', /\bsenior\b|\bsr\.?\b/],
    ['manager', /\bmanager\b/],
    ['associate', /\b(associate|junior)\b/],
  ],
  function: [
    ['product', /\bproduct (manager|owner|director|lead|management)\b|\bproduct\b/],
    ['growth', /\bgrowth\b/],
    ['engineering', /\b(engineer|engineering|developer|software)\b/],
    ['design', /\b(designer|ux|user experience)\b/],
    ['data', /\b(data|analytics|analyst)\b/],
    ['marketing', /\bmarketing\b/],
    ['operations', /\b(operations|ops)\b/],
    ['strategy', /\b(strategy|strategist)\b/],
  ],
  sector: [
    ['pharma', /\b(pharma|pharmaceutical|drug|clinical)\b/],
    ['health', /\b(health|healthcare|medical|patient|care)\b/],
    ['fintech', /\b(fintech|bank|banking|payments?|finance|financial)\b/],
    ['hosting', /\b(hosting|domains?|web host)\b/],
    ['ecommerce', /\b(e-?commerce|retail|marketplace)\b/],
    ['ai', /\b(ai|genai|llm|machine learning|ml)\b/],
    ['saas', /\b(saas|b2b software|platform)\b/],
    ['consulting', /\b(consultancy|consulting)\b/],
  ],
};

const LISTS = { seniority: SENIORITY, function: FUNCTION, sector: SECTOR };

// Seniority and function are read from the title area (the first 300
// characters), falling back to the whole text; a long JD mentions every
// seniority word somewhere. Sector is the label with the most hits across
// the whole text when the title area names none, since one "care" in a
// bank's benefits list is noise.
const TITLE_CHARS = 300;

function firstMatch(rules, t) {
  const hit = rules.find(([, re]) => re.test(t));
  return hit ? hit[0] : null;
}
function mostHits(rules, t) {
  let best = null, bestN = 0;
  for (const [label, re] of rules) {
    const n = (t.match(new RegExp(re.source, 'g')) || []).length;
    if (n > bestN) { best = label; bestN = n; }
  }
  return best;
}

// { seniority, function, sector }, every value from its fixed list.
export function classifyBrief(text) {
  const t = String(text || '').toLowerCase();
  const head = t.slice(0, TITLE_CHARS);
  const out = {
    seniority: firstMatch(RULES.seniority, head) || firstMatch(RULES.seniority, t),
    function: firstMatch(RULES.function, head) || firstMatch(RULES.function, t),
    sector: firstMatch(RULES.sector, head) || mostHits(RULES.sector, t),
  };
  for (const field of Object.keys(out)) {
    if (!out[field] || !LISTS[field].includes(out[field])) out[field] = 'unknown';
  }
  return out;
}
