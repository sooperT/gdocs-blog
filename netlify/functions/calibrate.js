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
import { retrieve as defaultRetrieve, listSections as defaultListSections, isProofPoint } from './lib/retrieval.js';
import { isDbEnvError } from './lib/db_env.js';
import {
  agentSideEnabled, AGENT_OFF_ERROR, createRateLimiter, createSectionMap, readTextBody,
  checkRequirementCount, stripInjection, isInjectionLine, applyDenyList, validateRows, dropUnknownSections,
} from './lib/guard.js';
import { classifyBrief } from './lib/role_shape.js';
import { cleanAnswer, deriveYear, deriveStrength, SELF_REPORTED, HUMAN_VERSION } from './ask.js';
import { referencesFor } from './lib/references.js';

export const MAX_BRIEF_CHARS = 12000;   // real JDs run to 8,500 (Sword Health, 2026-10-12)
export const MAX_REQUIREMENTS = 12;
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
  'At most 12 items, in the order they appear in the brief.',
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
  try { parsed = JSON.parse(text); } catch { return null; }
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

export function trimEvidence(answer, max = EVIDENCE_CHARS) {
  return answer.length <= max ? answer : answer.slice(0, max).trimEnd() + '...';
}

// Rule: below threshold -> "not met". Above threshold -> "met" when the
// section states a year (deriveYear) AND a direct outcome (hasOutcome:
// a quantified result or an outcome verb), otherwise "partial".
const NO_STAR = { kind: null, evidence_star: null, role: null, product: null, page: null, skills: null };

// A STAR row (PP.<n> chunk, item 31): evidence is the result cell, the section
// is the result's section id (always in the map), evidence_star carries the
// four cells. met: a result counts as an outcome, so year decides.
function buildProofPointRow(requirement, match) {
  const r = match.row;
  const cell = (k) => (r[k] && typeof r[k].text === 'string' ? r[k].text : null);
  const section = r.result?.section || r.product?.section;
  const result = cell('result');
  const year = cell('year') ? deriveYear(cell('year')) || cell('year') : null;
  return {
    requirement,
    met: year && result ? 'met' : 'partial',
    evidence: result ? trimEvidence(applyDenyList(result).text) : null,
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
  const year = deriveYear(answer);
  return {
    requirement,
    met: year && hasOutcome(answer) ? 'met' : 'partial',
    evidence: trimEvidence(answer),
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
    return { brief: url.searchParams.get('brief') || '', asker: url.searchParams.get('asker') };
  }
  const body = await readTextBody(request);
  if (body.status) return body;
  if (body.kind === 'json') {
    let parsed;
    try { parsed = JSON.parse(body.raw || '{}'); } catch { return { status: 400, error: 'Body is not valid JSON.' }; }
    const shapeOk = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      && (parsed.brief === undefined || typeof parsed.brief === 'string')
      && (parsed.asker === undefined || parsed.asker === null || typeof parsed.asker === 'string');
    if (!shapeOk) return { status: 415, error: 'JSON body must be {"brief": "<text>", "asker": "<optional text>"}.' };
    return { brief: parsed.brief || '', asker: parsed.asker || url.searchParams.get('asker') };
  }
  return { brief: body.raw, asker: url.searchParams.get('asker') };
}

export function createCalibrateHandler({
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
    const qIgnored = Boolean((url.searchParams.get('q') || '').trim());

    try {
      const split = runEnv.ANTHROPIC_API_KEY
        ? await splitBriefLLM(brief, { createMessage, max: Infinity })
        : { requirements: splitBriefHeuristic(brief, { max: Infinity }), splitter: 'heuristic' };
      const tooMany = checkRequirementCount(split.requirements.length);
      if (tooMany) return json({ error: tooMany.error, requirements: tooMany.requirements, usage: USAGE }, tooMany.status);
      const requirements = split.requirements.slice(0, MAX_REQUIREMENTS);
      const { splitter } = split;
      // Item 32: evidence queries per requirement (one Claude call; none without a key).
      const queries = runEnv.ANTHROPIC_API_KEY ? await evidenceQueries(requirements, { createMessage }) : requirements.map(() => []);

      // Small batches so 12 requirements x up to 3 texts don't hit Voyage all at once.
      let rows = [];
      for (let i = 0; i < requirements.length; i += 2) {
        const batch = requirements.slice(i, i + 2);
        // Item 31: sections and STAR rows compete; the best match wins. Item 32:
        // the requirement and its evidence queries all retrieve; matches merge.
        const results = await Promise.all(batch.map(async (r, j) => {
          const texts = [r, ...(queries[i + j] || [])];
          const rs = await Promise.all(texts.map(t => retrieve(t, { env: runEnv, kinds: 'all', topK: 5 })));
          if (rs.some(x => x?.error)) return { error: 'embedding failed' };
          const matches = mergeMatches(rs);
          // A retrieve stub (or an old shape) may carry only `match`: keep it.
          return { matches, match: matches[0] || rs[0]?.match || null };
        }));
        if (results.some(r => r?.error)) {
          console.error('[ask:brief] retrieval error');
          return json({ error: 'Retrieval is unavailable right now. Please try again later.', human_version: HUMAN_VERSION }, 503);
        }
        batch.forEach((r, j) => rows.push(buildRow(r, pickMatch(results[j].matches) || results[j].match)));
      }

      // Outgoing guard: sections outside the map, deny-list, schema.
      const { ids } = await map.get();
      rows = dropUnknownSections(rows, ids).rows;
      let withheld = 0;
      rows = rows.map(r => {
        const d = applyDenyList(r.evidence);
        withheld += d.withheld;
        return d.withheld ? { ...r, evidence: d.text } : r;
      });
      rows = validateRows(rows, { tag: '[ask:brief]' }).rows;

      const count = (m) => rows.filter(r => r.met === m).length;
      // Guardrail 8: counts and three fixed-list labels (item 27), never the
      // brief or the requirements.
      const shape = classifyBrief(brief);
      console.log('[ask:brief]', JSON.stringify({
        asker, requirements: rows.length, met: count('met'), partial: count('partial'), not_met: count('not met'), splitter,
        proof_point_rows: rows.filter(r => r.kind === 'proof-point').length,
        evidence_queries: queries.reduce((n, q) => n + q.length, 0),
        seniority: shape.seniority, function: shape.function, sector: shape.sector,
      }));

      return json({
        brief: { requirements: rows.length, splitter },
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
