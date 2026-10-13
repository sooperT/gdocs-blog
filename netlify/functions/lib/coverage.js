// Role context (Tom, 2026-10-13): a domain ("health-tech"), an environment
// ("founder-led startup", "40-person company") or a level ("Head of Product")
// is a property of a role and its company, and it adds up over a career. One
// story cannot answer it. Such a requirement is answered from the roles
// register (lib/roles.json, written by generate_agent_page.py): every role
// that matches, with its years and Tom's own line. No retrieval, no score.
import DATA from './roles.json' with { type: 'json' };

// A requirement that is the dimension itself ("Health-tech experience",
// "Experience in a founder-led startup") becomes a coverage row. One that asks
// for something more ("Hands-on GenAI experience in pharma") keeps its story
// row and carries the coverage beside it: at most this many words may be left
// once the dimension phrases and the filler are taken out.
export const COVERAGE_RESIDUE_WORDS = 1;
const FILLER = /\b(?:experienced?|background|track record|proven|strong|solid|prior|previous|relevant|demonstrated|significant|extensive|years?|working|worked|work|within|in|at|a|an|the|of|or|and|for|from|with|as|is|are|to|have|has|you|your|our|we|role|roles|position|company|companies|business|organi[sz]ations?|environments?|industry|sector|space|settings?|required|requirement|preferred|ideally|essential|must|should|plus|nice|b2b|b2c|similar|comparable|size|sized|stage|level|title|seniority)\b/gi;
export const COVERAGE_NOTE = 'Every role in Tom\'s record that matches, not one story: count them all. `also` holds example stories from those roles.';
export const SIZE_NOTE = 'Company sizes from Tom\'s record, nearest first. A fact, not a verdict: compare it with the requirement yourself.';

const DIMENSIONS = ['sector', 'environment', 'level'];
const compiled = new WeakMap();
function patterns(data) {
  if (!compiled.has(data)) {
    const dims = DIMENSIONS.flatMap(d => (data.dimensions?.[d] || []).map(e => ({ dimension: d, id: e.id, label: e.label, res: (e.asks || []).map(a => new RegExp(a, 'i')) })));
    compiled.set(data, { dims, size: data.size_ask ? new RegExp(data.size_ask, 'i') : null });
  }
  return compiled.get(data);
}

// What a requirement asks about: [{dimension, id, label}] plus {dimension: 'size', people}.
export function classifyCoverage(requirement, data = DATA) {
  const text = String(requirement || '');
  if (!text.trim()) return [];
  const { dims, size } = patterns(data);
  const out = dims.filter(d => d.res.some(re => re.test(text))).map(({ dimension, id, label }) => ({ dimension, id, label }));
  const m = size && text.match(size);
  if (m) {
    const people = Number(m[1].replace(/,/g, ''));
    if (people > 0) out.push({ dimension: 'size', id: 'size', label: `Company size (asked: ${m[1]})`, people });
  }
  return out;
}

const companyEntry = (c, detail, section) => ({ company: c.company, role: null, years: c.years, detail: detail || null, section: section || c.section, page: c.page });

function entriesFor(ask, data) {
  const companies = data.companies || [];
  if (ask.dimension === 'sector') {
    return companies.filter(c => c.sectors.includes(ask.id))
      .map(c => companyEntry(c, c.products.length ? c.products.join(', ') : c.context?.text));
  }
  if (ask.dimension === 'environment') {
    return companies.filter(c => c.environments.includes(ask.id))
      .map(c => companyEntry(c, [c.context?.text, c.size?.text].filter(Boolean).join(' '), c.context?.section));
  }
  if (ask.dimension === 'level') {
    return companies.flatMap(c => c.roles.filter(r => r.levels.includes(ask.id))
      .map(r => ({ company: c.company, role: r.role, years: r.years, detail: r.scope.text, section: r.scope.section, page: r.page })));
  }
  // size: every company that states one, the nearest headcount first
  const distance = (c) => Math.min(...c.size.people.map(n => Math.abs(Math.log(n / ask.people))));
  return companies.filter(c => c.size).sort((a, b) => distance(a) - distance(b))
    .map(c => companyEntry(c, c.size.text, c.size.section));
}

const line = (e) => `${e.role ? (e.role.includes(e.company) ? e.role : `${e.role}, ${e.company}`) : e.company} (${e.years})${e.detail ? `: ${e.detail.replace(/[.\s]+$/, '')}` : ''}`;

// { groups, evidence, section, year, companies, sizeOnly } for a requirement,
// or null when it asks no dimension Tom's record has a role for.
export function coverageFor(requirement, data = DATA) {
  const groups = classifyCoverage(requirement, data)
    .map(ask => ({ dimension: ask.dimension, id: ask.id, label: ask.label, roles: entriesFor(ask, data) }))
    .filter(g => g.roles.length);
  if (!groups.length) return null;
  // A company already described under an earlier dimension is named, not described again.
  const said = new Set();
  const once = (e) => { const key = `${e.company}|${e.detail}`; const again = said.has(key); said.add(key); return again ? line({ ...e, detail: null }) : line(e); };
  const evidence = groups.map(g => `${g.label}: ${g.roles.map(once).join('; ')}.`).join(' ');
  const years = groups.length === 1 ? groups[0].roles.flatMap(e => e.years.match(/\d{4}/g) || []).map(Number) : [];
  const first = Math.min(...years), last = Math.max(...years);
  return {
    groups,
    evidence,
    section: groups[0].roles[0].section,
    // The span the matching roles cover, first year to last; not a count of years.
    year: !years.length || groups[0].dimension === 'size' ? null : (first === last ? String(first) : `${first}-${last}`),
    companies: new Set(groups.filter(g => g.dimension !== 'size').flatMap(g => g.roles.map(e => e.company))),
    sizeOnly: groups.every(g => g.dimension === 'size'),
  };
}

export function isCoverageRequirement(requirement, data = DATA) {
  const { dims, size } = patterns(data);
  let text = String(requirement || '');
  for (const re of [...dims.flatMap(d => d.res), ...(size ? [size] : [])]) text = text.replace(new RegExp(re.source, 'gi'), ' ');
  const left = text.replace(FILLER, ' ').replace(/[^a-z\s]/gi, ' ').split(/\s+/).filter(Boolean);
  return left.length <= COVERAGE_RESIDUE_WORDS;
}
