// Brief calibration (PRD W4): paste a job brief, get one evidence row per
// requirement in Tend's grammar. Evidence only: no summary, no adjectives,
// no overall score. Each requirement runs through the shared TomBot
// retrieval once.
//
// Routes: GET /ask?brief=... (delegated from ask.js), and GET or POST
// /ask/brief (netlify.toml). POST takes a JSON body {"brief": "...",
// "asker": "..."} or the raw brief as text/plain.
// Guardrails (lib/guard.js): switch-off, rate limit, 64 KB body cap, text
// bodies only, 25 requirements max, injection lines stripped and flagged,
// schema validation, deny-list on evidence, sections outside the map dropped.
import Anthropic from '@anthropic-ai/sdk';
import { envForRequest } from './lib/db_env.js';
import { retrieve as defaultRetrieve, listSections as defaultListSections, isProofPoint, QUESTION_MATCH_THRESHOLD, prepareAgentQuery } from './lib/retrieval.js';
import { isDbEnvError } from './lib/db_env.js';
import {
  agentSideEnabled, AGENT_OFF_ERROR, createRateLimiter, createSectionMap, readTextBody,
  checkRequirementCount, stripInjection, isInjectionLine, applyDenyList, validateRows, dropUnknownSections, AGENT_HIDDEN_SECTIONS,
} from './lib/guard.js';
import { classifyBrief } from './lib/role_shape.js';
import { cleanAnswer, deriveYear, deriveStrength, SELF_REPORTED, HUMAN_VERSION } from './ask.js';
import { referencesFor } from './lib/references.js';
import { classifyKnockouts, answerFor, FACT_NOTE, NOT_STATED_NOTE } from './lib/facts.js';
import SECTION_YEARS from './lib/section_years.json' with { type: 'json' };
import { logUsage, getUsagePool, cleanTag } from './lib/usage.js';

export const MAX_BRIEF_CHARS = 12000;   // real JDs run to 8,500 (Sword Health, 2026-10-12)
export const MAX_REQUIREMENTS = 16;   // 12 dropped half the Sword Health JD (run 3b, 2026-10-12)
export const EVIDENCE_CHARS = 400;
const NOTE = "Evidence only. 'not met' means TomBot content has nothing on it, not that Tom lacks it.";
const NOTE_Q_IGNORED = ' Both q and brief were given; brief was used and q was ignored.';
const USAGE = 'Usage: GET /ask?brief=<job brief>, or POST /ask/brief with {"brief": "..."} (application/json) or the brief as text/plain. Optional asker=<recruiter-agent | hiring-manager | human>. Max 12000 characters.';

// Same model and client pattern as chat.js. No temperature: claude-sonnet-5
// rejects sampling parameters with a 400, so determinism comes from the
// fixed prompt instead.
export const SPLITTER_MODEL = 'claude-sonnet-5';
export const SPLITTER_SYSTEM_PROMPT = [
  'You split a job brief into its separate requirements.',
  'Return only a JSON array of strings and nothing else: no prose, no code fences.',
  "Each string is one requirement, copied in the brief's own words. Do not paraphrase, summarise, merge or add anything.",
  'Include skills, experience, qualifications, languages, location and working-pattern conditions.',
  'Leave out company descriptions, benefits and application instructions.',
  'At most 16 items, in the order they appear in the brief.',
].join('\n');

function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...extraHeaders,
    },
  });
}

const normKey = (s) => s.toLowerCase().replace(/\s+/g, ' ').replace(/[\s.;:,!]+$/, '').trim();

function dedupeCap(items, max = MAX_REQUIREMENTS) {
  const seen = new Set();
  const out = [];
  for (const raw of items) {
    if (typeof raw !== 'string') continue;
    const item = raw.replace(/\s+/g, ' ').trim();
    const key = normKey(item);
    if (key.length < 3 || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= max) break;
  }
  return out;
}

const BULLET = /^\s*(?:[-*•·▪◦‣–—]|\(?\d{1,2}[.)])\s+(.+)$/;
const KEYWORD = /\b(?:must|should|required|requires?|requirements?|experience[d]?|years?|fluent|fluency)\b/i;

// (a) Heuristic: bullet and numbered lines as-is, plus any other sentence
// containing must / should / required / experience / years / fluent.
// `max` defaults to 12; the handler passes Infinity to count first (guard: 25).
export function splitBriefHeuristic(text, { max = MAX_REQUIREMENTS } = {}) {
  const items = [];
  for (const line of String(text || '').split(/\r?\n/)) {
    const bullet = line.match(BULLET);
    if (bullet) { items.push(bullet[1]); continue; }
    for (const sentence of line.split(/(?<=[.!?])\s+/)) {
      if (KEYWORD.test(sentence)) items.push(sentence);
    }
  }
  return dedupeCap(items, max);
}

// Pull a JSON array of strings out of a model reply. null if malformed.
export function parseRequirementArray(reply, { max = MAX_REQUIREMENTS } = {}) {
  let s = String(reply || '').trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  const start = s.indexOf('[');
  const end = s.lastIndexOf(']');
  if (start === -1 || end <= start) return null;
  try {
    const arr = JSON.parse(s.slice(start, end + 1));
    if (!Array.isArray(arr) || !arr.every(x => typeof x === 'string')) return null;
    const out = dedupeCap(arr, max);
    return out.length ? out : null;
  } catch {
    return null;
  }
}

let defaultClient = null;
function defaultCreateMessage(params) {
  if (!defaultClient) defaultClient = new Anthropic();
  return defaultClient.messages.create(params);
}

// (b) LLM: one Claude call. Returns { requirements, splitter }; falls back
// to the heuristic (and says so) on an API error or a malformed reply.
export async function splitBriefLLM(text, { createMessage = defaultCreateMessage, max = MAX_REQUIREMENTS } = {}) {
  try {
    const msg = await createMessage({
      model: SPLITTER_MODEL,
      max_tokens: 1024,
      thinking: { type: 'disabled' },
      system: SPLITTER_SYSTEM_PROMPT,
      messages: [{ role: 'user', content: String(text) }],
    });
    const reply = (msg?.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
    const parsed = parseRequirementArray(reply, { max });
    if (parsed) return { requirements: parsed, splitter: 'llm' };
    console.error('[ask:brief] splitter reply malformed, using heuristic');
  } catch (error) {
    console.error('[ask:brief] splitter call failed, using heuristic:', error?.status || error?.name || 'error');
  }
  return { requirements: splitBriefHeuristic(text, { max }), splitter: 'heuristic' };
}

// Item 32: evidence queries. Requirements are abstract ("set the quality bar
// and instrument it"); proof points are concrete ("doubled labelling
// throughput"). One more Claude call rewrites each requirement as up to two
// short queries phrased the way a CV line reads, using only the requirement's
// own nouns. Retrieval then runs the requirement and its queries and keeps
// the best match. Any failure -> no queries, the requirement alone.
export const EVIDENCE_SYSTEM_PROMPT = [
  'You rewrite job requirements as short search queries for a database of one person\'s past work.',
  'Input: a JSON array of requirement strings. Output: only a JSON array of the same length, each entry an array of up to two query strings. No prose, no code fences.',
  'Each query is a concrete past-tense phrase the way a CV line reads: "built a ...", "led a ... team", "reduced ... by", "launched ...".',
  'Use only nouns and verbs from the requirement; add no facts, no names, no numbers. Keep each query under 15 words.',
  'An empty array is fine when a requirement has no concrete form (for example "taste and judgement").',
].join('\n');
export const MAX_EVIDENCE_QUERIES = 2;
export const MAX_EVIDENCE_QUERY_CHARS = 120;

export function parseEvidenceQueries(reply, count, { max = MAX_EVIDENCE_QUERIES } = {}) {
  if (typeof reply !== 'string') return null;
  const text = reply.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  let parsed;
  try { parsed = JSON.parse(text); } catch {
    // The model sometimes drops the outer brackets: ["a"], ["b"], [] (Novonesis, 2026-10-12).
    try { parsed = JSON.parse(`[${text}]`); } catch { return null; }
  }
  if (!Array.isArray(parsed) || parsed.length !== count) return null;
  return parsed.map(entry => (Array.isArray(entry) ? entry : [])
    .filter(q => typeof q === 'string' && q.trim() && !isInjectionLine(q))
    .map(q => q.trim().slice(0, MAX_EVIDENCE_QUERY_CHARS))
    .slice(0, max));
}

export async function evidenceQueries(requirements, { createMessage = defaultCreateMessage } = {}) {
  const empty = requirements.map(() => []);
  if (!requirements.length) return empty;
  try {
    const msg = await createMessage({
      model: SPLITTER_MODEL,
      max_tokens: 1024,
      thinking: { type: 'disabled' },
      system: EVIDENCE_SYSTEM_PROMPT,
      messages: [{ role: 'user', content: JSON.stringify(requirements) }],
    });
    const reply = (msg?.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
    const parsed = parseEvidenceQueries(reply, requirements.length);
    if (parsed) return parsed;
    console.error('[ask:brief] evidence queries malformed, using requirements only');
  } catch (error) {
    console.error('[ask:brief] evidence queries call failed, using requirements only:', error?.status || error?.name || 'error');
  }
  return empty;
}

// Adjacent evidence (Tom, 2026-10-12): a requirement with no match above the
// threshold may still have transferable evidence just below it. The row keeps
// its mechanical met / partial / not met; `adjacent` carries the nearest
// evidence when its score is in [ADJACENT_MIN, threshold), labelled as such.
// The brief endpoint's own threshold (chat and /ask keep 0.55): job-description
// prose scores 0.50 to 0.58 against routes, so 0.55 flipped rows between runs
// on a hundredth of a point (Sword Health, 2026-10-12). Adjacent covers the
// band just under it.
export const BRIEF_THRESHOLD = 0.50;
export const ADJACENT_MIN = 0.42;
export const ADJACENT_NOTE = 'Nearest evidence, below the match threshold: transferable at most, not a match.';

export function nearestBelowThreshold(results, { threshold = BRIEF_THRESHOLD, min = ADJACENT_MIN } = {}) {
  let best = null;
  for (const r of results) {
    const t = r?.topMatch;
    if (!t || typeof t.similarity !== 'number') continue;
    if (t.similarity >= threshold || t.similarity < min) continue;
    if (!best || t.similarity > best.similarity) best = t;
  }
  return best;
}

export function buildAdjacent(match) {
  if (!match) return null;
  const row = buildRow('', match);
  // Floored, not rounded: 0.4996 must not print as 0.5, the threshold it is below.
  const score = Math.floor(Number(match.similarity) * 100 + 1e-9) / 100;
  return {
    evidence: row.evidence, section: row.section, source: row.source, score, year: row.year,
    kind: row.kind, product: row.product, page: row.page, note: ADJACENT_NOTE,
  };
}

// Merge the matches of a requirement and its queries: best similarity per title.
export function mergeMatches(results) {
  const byTitle = new Map();
  for (const r of results) {
    for (const m of (r?.matches || [])) {
      const prev = byTitle.get(m.title);
      if (!prev || Number(m.similarity) > Number(prev.similarity)) byTitle.set(m.title, m);
    }
  }
  return [...byTitle.values()].sort((a, b) => Number(b.similarity) - Number(a.similarity));
}

const OUTCOME = /\d+(?:[.,]\d+)?\s*(?:%|x\b|k\b|m\b|bn\b|million|billion|users|customers|patients|people|countries|markets|teams?)|\b(?:launched|shipped|grew|increased|reduced|cut|doubled|tripled|delivered|acquired|won|saved|raised|turned around)\b/i;

export function hasOutcome(answer) {
  return OUTCOME.test(String(answer || ''));
}

// Evidence is prose for a table cell: no markdown bold, no table rows, no
// list markers, one paragraph. A section that is only a table (META.JOBS)
// yields its first non-table line, else an empty string.
export function plainEvidence(text) {
  const lines = String(text || '').split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('|') && !/^-{3,}$/.test(l));
  return lines.map(l => l.replace(/\*\*/g, '').replace(/^[-*]\s+/, '').replace(/^#+\s+/, '')).join(' ').replace(/\s+/g, ' ').trim();
}

export function trimEvidence(answer, max = EVIDENCE_CHARS) {
  return answer.length <= max ? answer : answer.slice(0, max).trimEnd() + '...';
}

// Rule: below threshold -> "not met". Above threshold -> "met" when the
// section states a year (deriveYear) AND a direct outcome (hasOutcome:
// a quantified result or an outcome verb), otherwise "partial".
export function sectionYear(title, table = SECTION_YEARS) {
  const years = table && table.years;
  if (typeof title !== 'string' || !years || !Object.prototype.hasOwnProperty.call(years, title)) return null;
  const y = deriveYear(years[title]);
  return y || years[title] || null;
}

const NO_STAR = { kind: null, evidence_star: null, role: null, product: null, page: null, skills: null, adjacent: null, fact_type: null, fact_types: null, also: null, facet: null };

// More than one example (Tom, 2026-10-12): the other STAR rows that cleared
// the threshold for this requirement, a different product each, best first.
// One story answering three requirements reads as one story; a reader weighing
// a must-have looks for a second.
export const MAX_ALSO = 2;
export function alsoRows(matches, chosen, { max = MAX_ALSO } = {}) {
  const taken = new Set([chosen?.row?.product?.text].filter(Boolean));
  const out = [];
  for (const m of (matches || [])) {
    if (m === chosen || !isProofPoint(m.title) || !m.row || typeof m.row !== 'object') continue;
    const product = m.row.product?.text;
    if (!product || taken.has(product) || !m.row.result?.text) continue;
    taken.add(product);
    const r = buildProofPointRow('', m, { facets: false });   // the result cell: the appendix finds the row by it
    out.push({ evidence: r.evidence, role: r.role, product: r.product, year: r.year, section: r.section, page: r.page, score: r.score });
    if (out.length === max) break;
  }
  return out.length ? out : null;
}

// A knockout (R1012-22): the fact, in Tom's words, next to the requirement. No
// verdict: `met` is "fact" (the reader compares) or "not stated" (no fact on
// record; `evidence` carries what to do about it, there is nothing to cite).
// A line that asks several facts (N1012-15) gets each stated one, labelled;
// `fact_type` stays the first, `fact_types` lists all.
export function buildFactRow(requirement, facts) {
  const all = Array.isArray(facts) ? facts : [facts];
  const said = all.map(f => ({ f, a: answerFor(requirement, f) })).filter(x => x.a !== null);
  const fact = said.length ? said[0].f : all[0];
  const answer = said.length > 1 ? said.map(x => `${x.f.label}: ${x.a.replace(/\.$/, '')}`).join('. ') + '.'
    : said.length ? said[0].a : null;
  const stated = answer !== null;
  return {
    requirement,
    met: stated ? 'fact' : 'not stated',
    evidence: answer,
    strength: null,
    year: null,
    section: stated ? fact.section : null,
    source: stated && fact.section ? `TomBot ${fact.section}` : null,
    tier: stated ? SELF_REPORTED : null,
    score: null,
    references: null,
    ...NO_STAR,
    kind: 'fact',
    fact_type: all[0].type,
    fact_types: all.map(f => f.type),
    note: stated ? FACT_NOTE : NOT_STATED_NOTE,
  };
}

// Story facets (R1013-2, N1012-14): a row carries Tom's own CV lines, each
// embedded as a route term. When the term that matched (question_text) is a
// facet's line, one of its variants, or what it answers, that facet is the
// evidence: the same story, the face Tom shows this kind of ad. The result
// cell stays in evidence_star and still decides met / partial.
export function matchedFacet(row, questionText) {
  const facets = Array.isArray(row?.facets) ? row.facets : [];
  const q = typeof questionText === 'string' ? questionText.trim() : '';
  if (!q) return null;
  const same = (s) => typeof s === 'string' && s.trim() === q;
  return facets.find(f => same(f.text) || same(f.answers) || (Array.isArray(f.variants) && f.variants.some(v => same(v.text)))) || null;
}

// A STAR row (PP.<n> chunk, item 31): evidence is the result cell, or the facet
// that matched; the section is the result's section id (always in the map),
// evidence_star carries the four cells. met: a result counts as an outcome, so
// year decides.
function buildProofPointRow(requirement, match, { facets = true } = {}) {
  const r = match.row;
  const cell = (k) => (r[k] && typeof r[k].text === 'string' ? r[k].text : null);
  const section = r.result?.section || r.product?.section;
  const result = cell('result');
  const year = cell('year') ? deriveYear(cell('year')) || cell('year') : null;
  const facet = facets ? matchedFacet(r, match.question_text) : null;
  const line = facet && typeof facet.text === 'string' ? facet.text : result;
  return {
    requirement,
    met: year && result ? 'met' : 'partial',
    evidence: line ? trimEvidence(applyDenyList(line).text) : null,
    strength: r.strength || null,
    year,
    section,
    source: `TomBot ${section}`,
    tier: SELF_REPORTED,
    score: Math.round(Number(match.similarity) * 100) / 100,
    references: referencesFor(section),
    kind: 'proof-point',
    evidence_star: { situation: cell('situation'), task: cell('task'), action: cell('action'), result },
    role: cell('role'),
    product: cell('product'),
    page: r.page || null,
    skills: Array.isArray(r.skills) ? r.skills : [],
    adjacent: null,
    fact_type: null,
    fact_types: null,
    also: null,
    facet: facet ? { id: facet.id || null, label: facet.label || null, source: facet.source || null, tier: facet.tier || SELF_REPORTED } : null,
  };
}

// Item 31: a STAR row is the better evidence when it clears the threshold, even
// if a chat section (dozens of hand-written routes) scores a little higher.
// Pick the best row within PP_MARGIN of the best match; else the best match.
export const PP_MARGIN = 0.2;
export function pickMatch(matches, { margin = PP_MARGIN } = {}) {
  if (!Array.isArray(matches) || !matches.length) return null;
  const best = matches[0];
  const row = matches.find(m => isProofPoint(m.title) && m.row && typeof m.row === 'object');
  if (row && row !== best && Number(row.similarity) >= Number(best.similarity) - margin) return row;
  return best;
}

export function buildRow(requirement, match) {
  if (!match) {
    // No evidence, so no tier and no references.
    return { requirement, met: 'not met', evidence: null, strength: null, year: null, section: null, source: null, tier: null, score: null, references: null, ...NO_STAR };
  }
  if (isProofPoint(match.title) && match.row && typeof match.row === 'object') {
    return buildProofPointRow(requirement, match);
  }
  const answer = cleanAnswer(match.content);
  // A section's own year, else the year of the role it sits under (lib/section_years.json).
  const year = deriveYear(answer) || sectionYear(match.title);
  const evidence = trimEvidence(answer);
  // A table-only section (META.JOBS) flattens to nothing: no evidence is no match.
  if (!plainEvidence(evidence)) return buildRow(requirement, null);
  return {
    requirement,
    met: year && hasOutcome(answer) ? 'met' : 'partial',
    evidence,
    strength: deriveStrength(match),
    year,
    section: match.title,
    source: `TomBot ${match.title}`,
    tier: SELF_REPORTED,
    score: Math.round(Number(match.similarity) * 100) / 100,
    references: referencesFor(match.title),
    ...NO_STAR,
    kind: 'section',
  };
}

// Returns { brief, asker } or { status, error }.
async function readBrief(request, url) {
  if (request.method === 'GET') {
    return { brief: url.searchParams.get('brief') || '', asker: url.searchParams.get('asker'), tag: url.searchParams.get('tag') };
  }
  const body = await readTextBody(request);
  if (body.status) return body;
  if (body.kind === 'json') {
    let parsed;
    try { parsed = JSON.parse(body.raw || '{}'); } catch { return { status: 400, error: 'Body is not valid JSON.' }; }
    const shapeOk = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      && (parsed.brief === undefined || typeof parsed.brief === 'string')
      && (parsed.asker === undefined || parsed.asker === null || typeof parsed.asker === 'string')
      && (parsed.tag === undefined || parsed.tag === null || typeof parsed.tag === 'string');
    if (!shapeOk) return { status: 415, error: 'JSON body must be {"brief": "<text>", "asker": "<optional text>", "tag": "<optional send tag>"}.' };
    return { brief: parsed.brief || '', asker: parsed.asker || url.searchParams.get('asker'), tag: parsed.tag || url.searchParams.get('tag') };
  }
  return { brief: body.raw, asker: url.searchParams.get('asker'), tag: url.searchParams.get('tag') };
}

export function createCalibrateHandler({
  usagePool,   // test seam; default: the shared pool when NILEDB_URL is set
  retrieve = defaultRetrieve,
  createMessage = defaultCreateMessage,
  env = process.env,
  listSections,
  limiter = createRateLimiter(),
  sectionMap,
} = {}) {
  let runEnv = env;   // pinned per request from the runtime deploy context (db_env.envForRequest)
  const map = sectionMap || createSectionMap({ listSections: listSections || (() => defaultListSections({ env: runEnv })) });
  return async (request, context) => {
    runEnv = envForRequest(env, context);
    if (!agentSideEnabled(runEnv)) return json({ error: AGENT_OFF_ERROR }, 503);
    if (request.method !== 'GET' && request.method !== 'POST') {
      return json({ error: 'Method not allowed. ' + USAGE }, 405, { 'Allow': 'GET, POST' });
    }
    if (limiter) {
      const rl = limiter.check(request);
      if (!rl.ok) return json({ error: 'Too many requests. Try again shortly.' }, 429, { 'Retry-After': String(rl.retryAfter) });
    }
    const url = new URL(request.url);
    const input = await readBrief(request, url);
    if (input.status) return json({ error: input.error, usage: USAGE }, input.status);
    if (input.brief.length > MAX_BRIEF_CHARS) {
      return json({ error: `Brief is longer than ${MAX_BRIEF_CHARS} characters.`, usage: USAGE }, 413);
    }
    if (!input.brief.trim()) return json({ error: 'Missing brief.', usage: USAGE }, 400);
    // Instruction-like lines are removed before anything reads the brief.
    const { text: stripped, lines: injectionLines } = stripInjection(input.brief);
    const flags = injectionLines ? ['injection_pattern'] : [];
    const brief = stripped.trim();
    if (!brief) {
      return json({ error: 'Brief has no requirements once instruction-like lines are removed.', flags, injection_lines: injectionLines, usage: USAGE }, 400);
    }
    const asker = input.asker ? String(input.asker).slice(0, 40) : null;
    const tag = cleanTag(input.tag);
    const qIgnored = Boolean((url.searchParams.get('q') || '').trim());

    try {
      const split = runEnv.ANTHROPIC_API_KEY
        ? await splitBriefLLM(brief, { createMessage, max: Infinity })
        : { requirements: splitBriefHeuristic(brief, { max: Infinity }), splitter: 'heuristic' };
      const tooMany = checkRequirementCount(split.requirements.length);
      if (tooMany) return json({ error: tooMany.error, requirements: tooMany.requirements, usage: USAGE }, tooMany.status);
      const allRequirements = split.requirements.slice(0, MAX_REQUIREMENTS);
      const { splitter } = split;
      // R1012-22: knockouts are answered from the facts register and never
      // reach retrieval; only experience requirements are matched to stories.
      const knockouts = allRequirements.map(r => classifyKnockouts(r));
      const requirements = allRequirements.filter((_, i) => !knockouts[i].length);
      // Item 32: evidence queries per requirement (one Claude call; none without a key).
      const queries = runEnv.ANTHROPIC_API_KEY && requirements.length ? await evidenceQueries(requirements, { createMessage }) : requirements.map(() => []);

      // Small batches so 12 requirements x up to 3 texts don't hit Voyage all at once.
      let rows = [];
      for (let i = 0; i < requirements.length; i += 2) {
        const batch = requirements.slice(i, i + 2);
        // Item 31: sections and STAR rows compete; the best match wins. Item 32:
        // the requirement and its evidence queries all retrieve; matches merge.
        const results = await Promise.all(batch.map(async (r, j) => {
          const texts = [r, ...(queries[i + j] || [])];
          const rs = await Promise.all(texts.map(t => retrieve(t, { env: runEnv, kinds: 'all', topK: 5, threshold: BRIEF_THRESHOLD, prepare: prepareAgentQuery, exclude: AGENT_HIDDEN_SECTIONS })));
          if (rs.some(x => x?.error)) return { error: 'embedding failed' };
          const matches = mergeMatches(rs);
          // A retrieve stub (or an old shape) may carry only `match`: keep it.
          return { matches, match: matches[0] || rs[0]?.match || null, nearest: nearestBelowThreshold(rs) };
        }));
        if (results.some(r => r?.error)) {
          console.error('[ask:brief] retrieval error');
          return json({ error: 'Retrieval is unavailable right now. Please try again later.', human_version: HUMAN_VERSION }, 503);
        }
        batch.forEach((r, j) => {
          const chosen = pickMatch(results[j].matches) || results[j].match;
          const row = buildRow(r, chosen);
          if (row.met === 'not met' && results[j].nearest) row.adjacent = buildAdjacent(results[j].nearest);
          if (row.met !== 'not met') row.also = alsoRows(results[j].matches, chosen);
          rows.push(row);
        });
      }
      // Back into the brief's order, the fact rows in their places.
      const matched = rows;
      rows = [];
      allRequirements.forEach((r, i) => rows.push(knockouts[i].length ? buildFactRow(r, knockouts[i]) : matched.shift()));

      // Outgoing guard: sections outside the map, deny-list, schema.
      // Every requirement keeps its row: one the guard cannot pass becomes "not met".
      const { ids } = await map.get();
      let guarded = 0;
      const unmatched = (r) => { guarded++; return buildRow(r.requirement, null); };
      rows = rows.map(r => (dropUnknownSections([r], ids).rows.length ? r : unmatched(r)));
      let withheld = 0;
      rows = rows.map(r => {
        const d = applyDenyList(r.evidence);
        withheld += d.withheld;
        let out = d.withheld ? { ...r, evidence: d.text } : r;
        if (out.adjacent && out.adjacent.evidence) {
          const a = applyDenyList(out.adjacent.evidence);
          withheld += a.withheld;
          if (a.withheld) out = { ...out, adjacent: { ...out.adjacent, evidence: a.text } };
          if (!ids.has(out.adjacent.section)) out = { ...out, adjacent: null };
        }
        // Prose for a table cell, after the per-line deny-list has run.
        if (out.evidence && out.kind !== 'fact') out = { ...out, evidence: plainEvidence(out.evidence) };
        if (out.adjacent && out.adjacent.evidence) out = { ...out, adjacent: { ...out.adjacent, evidence: plainEvidence(out.adjacent.evidence) } };
        if (out.also) {
          const kept = out.also.filter(x => ids.has(x.section)).map(x => {
            const d2 = applyDenyList(x.evidence || '');
            withheld += d2.withheld;
            return { ...x, evidence: plainEvidence(d2.text) };
          });
          out = { ...out, also: kept.length ? kept : null };
        }
        // A table-only section (META.JOBS) flattens to nothing: no story, no adjacent.
        if (out.adjacent && !out.adjacent.evidence) out = { ...out, adjacent: null };
        return out;
      });
      rows = rows.map(r => (validateRows([r], { tag: '[ask:brief]' }).rows.length ? r : unmatched(r)));
      if (guarded) console.error('[ask:brief]', JSON.stringify({ rule: 'row_replaced_not_met', rows: guarded }));

      const count = (m) => rows.filter(r => r.met === m).length;
      // Guardrail 8: counts and three fixed-list labels (item 27), never the
      // brief or the requirements.
      const shape = classifyBrief(brief);
      const usage = {
        asker, tag, requirements: rows.length, met: count('met'), partial: count('partial'), not_met: count('not met'), splitter,
        proof_point_rows: rows.filter(r => r.kind === 'proof-point').length,
        evidence_queries: queries.reduce((n, q) => n + q.length, 0),
        adjacent: rows.filter(r => r.adjacent).length,
        // Fixed-list labels only: which knockout types the brief asked, and which had no fact.
        facts: rows.filter(r => r.kind === 'fact').flatMap(r => r.fact_types || [r.fact_type]),
        facts_not_stated: rows.filter(r => r.met === 'not stated').map(r => r.fact_type),
        seniority: shape.seniority, function: shape.function, sector: shape.sector,
      };
      console.log('[ask:brief]', JSON.stringify(usage));
      await logUsage({ pool: usagePool === undefined ? getUsagePool(runEnv) : usagePool, request, context, path: '/ask/brief', status: 200, meta: usage });

      return json({
        brief: { requirements: rows.length, splitter, evidence_queries: queries.reduce((n, q) => n + q.length, 0), threshold: BRIEF_THRESHOLD },
        rows,
        withheld,
        flags,
        injection_lines: injectionLines,
        human_version: HUMAN_VERSION,
        note: NOTE + (qIgnored ? NOTE_Q_IGNORED : ''),
      });
    } catch (error) {
      if (isDbEnvError(error)) {
        console.error('[ask:brief]', error.message);
        return json({ error: error.message, human_version: HUMAN_VERSION }, 503);
      }
      console.error('[ask:brief] error:', error?.name || 'error');
      return json({ error: 'Calibration failed. Please try again later.' }, 500);
    }
  };
}

export default createCalibrateHandler();

// Netlify-side limit, aggregated across instances (P-1011-1): same numbers as
// chat.js and the in-memory floor in lib/guard.js. No `path`: routing stays in
// netlify.toml.
export const config = {
  rateLimit: { windowLimit: 20, windowSize: 60, aggregateBy: ['ip'], action: 'rate_limit' },
};
