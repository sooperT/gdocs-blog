// Brief calibration (PRD W4): paste a job brief, get one evidence row per
// requirement in Tend's grammar. Evidence only: no summary, no adjectives,
// no overall score. Each requirement runs through the shared TomBot
// retrieval once.
//
// Routes: GET /ask?brief=... (delegated from ask.js), and GET or POST
// /ask/brief (netlify.toml). POST takes a JSON body {"brief": "...",
// "asker": "..."} or the raw brief as text/plain.
import Anthropic from '@anthropic-ai/sdk';
import { retrieve as defaultRetrieve, QUESTION_MATCH_THRESHOLD } from './lib/retrieval.js';
import { cleanAnswer, deriveYear, deriveStrength } from './ask.js';

export const MAX_BRIEF_CHARS = 8000;
export const MAX_REQUIREMENTS = 12;
export const EVIDENCE_CHARS = 400;
const MAX_BODY_BYTES = 64 * 1024;
const HUMAN_VERSION = '/projects/tombot/';
const NOTE = "Evidence only. 'not met' means TomBot content has nothing on it, not that Tom lacks it.";
const NOTE_Q_IGNORED = ' Both q and brief were given; brief was used and q was ignored.';
const USAGE = 'Usage: GET /ask?brief=<job brief>, or POST /ask/brief with {"brief": "..."} (application/json) or the brief as text/plain. Optional asker=<recruiter-agent | hiring-manager | human>. Max 8000 characters.';

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

function dedupeCap(items) {
  const seen = new Set();
  const out = [];
  for (const raw of items) {
    if (typeof raw !== 'string') continue;
    const item = raw.replace(/\s+/g, ' ').trim();
    const key = normKey(item);
    if (key.length < 3 || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= MAX_REQUIREMENTS) break;
  }
  return out;
}

const BULLET = /^\s*(?:[-*•·▪◦‣–—]|\(?\d{1,2}[.)])\s+(.+)$/;
const KEYWORD = /\b(?:must|should|required|requires?|requirements?|experience[d]?|years?|fluent|fluency)\b/i;

// (a) Heuristic: bullet and numbered lines as-is, plus any other sentence
// containing must / should / required / experience / years / fluent.
export function splitBriefHeuristic(text) {
  const items = [];
  for (const line of String(text || '').split(/\r?\n/)) {
    const bullet = line.match(BULLET);
    if (bullet) { items.push(bullet[1]); continue; }
    for (const sentence of line.split(/(?<=[.!?])\s+/)) {
      if (KEYWORD.test(sentence)) items.push(sentence);
    }
  }
  return dedupeCap(items);
}

// Pull a JSON array of strings out of a model reply. null if malformed.
export function parseRequirementArray(reply) {
  let s = String(reply || '').trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  const start = s.indexOf('[');
  const end = s.lastIndexOf(']');
  if (start === -1 || end <= start) return null;
  try {
    const arr = JSON.parse(s.slice(start, end + 1));
    if (!Array.isArray(arr) || !arr.every(x => typeof x === 'string')) return null;
    const out = dedupeCap(arr);
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
export async function splitBriefLLM(text, { createMessage = defaultCreateMessage } = {}) {
  try {
    const msg = await createMessage({
      model: SPLITTER_MODEL,
      max_tokens: 1024,
      thinking: { type: 'disabled' },
      system: SPLITTER_SYSTEM_PROMPT,
      messages: [{ role: 'user', content: String(text) }],
    });
    const reply = (msg?.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
    const parsed = parseRequirementArray(reply);
    if (parsed) return { requirements: parsed, splitter: 'llm' };
    console.error('[ask:brief] splitter reply malformed, using heuristic');
  } catch (error) {
    console.error('[ask:brief] splitter call failed, using heuristic:', error?.status || error?.name || 'error');
  }
  return { requirements: splitBriefHeuristic(text), splitter: 'heuristic' };
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
export function buildRow(requirement, match) {
  if (!match) {
    return { requirement, met: 'not met', evidence: null, strength: null, year: null, source: null, score: null };
  }
  const answer = cleanAnswer(match.content);
  const year = deriveYear(answer);
  return {
    requirement,
    met: year && hasOutcome(answer) ? 'met' : 'partial',
    evidence: trimEvidence(answer),
    strength: deriveStrength(match),
    year,
    source: `TomBot ${match.title}`,
    score: Math.round(Number(match.similarity) * 100) / 100,
  };
}

async function readBrief(request, url) {
  if (request.method === 'GET') {
    return { brief: url.searchParams.get('brief') || '', asker: url.searchParams.get('asker') };
  }
  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return { tooLarge: true };
  const type = (request.headers.get('content-type') || '').toLowerCase();
  if (type.includes('application/json')) {
    let body;
    try { body = JSON.parse(raw || '{}'); } catch { return { badJson: true }; }
    return {
      brief: typeof body?.brief === 'string' ? body.brief : '',
      asker: typeof body?.asker === 'string' ? body.asker : url.searchParams.get('asker'),
    };
  }
  return { brief: raw, asker: url.searchParams.get('asker') };
}

export function createCalibrateHandler({
  retrieve = defaultRetrieve,
  createMessage = defaultCreateMessage,
  env = process.env,
} = {}) {
  return async (request) => {
    if (request.method !== 'GET' && request.method !== 'POST') {
      return json({ error: 'Method not allowed. ' + USAGE }, 405, { 'Allow': 'GET, POST' });
    }
    const url = new URL(request.url);
    const input = await readBrief(request, url);
    if (input.badJson) return json({ error: 'Body is not valid JSON.', usage: USAGE }, 400);
    if (input.tooLarge || input.brief.length > MAX_BRIEF_CHARS) {
      return json({ error: `Brief is longer than ${MAX_BRIEF_CHARS} characters.`, usage: USAGE }, 413);
    }
    const brief = input.brief.trim();
    if (!brief) return json({ error: 'Missing brief.', usage: USAGE }, 400);
    const asker = input.asker ? String(input.asker).slice(0, 40) : null;
    const qIgnored = Boolean((url.searchParams.get('q') || '').trim());

    try {
      const { requirements, splitter } = env.ANTHROPIC_API_KEY
        ? await splitBriefLLM(brief, { createMessage })
        : { requirements: splitBriefHeuristic(brief), splitter: 'heuristic' };

      // Small batches so 12 requirements don't hit Voyage all at once.
      const rows = [];
      for (let i = 0; i < requirements.length; i += 4) {
        const batch = requirements.slice(i, i + 4);
        const results = await Promise.all(batch.map(r => retrieve(r)));
        if (results.some(r => r?.error)) {
          console.error('[ask:brief] retrieval error');
          return json({ error: 'Retrieval is unavailable right now. Please try again later.', human_version: HUMAN_VERSION }, 503);
        }
        batch.forEach((r, j) => rows.push(buildRow(r, results[j].match)));
      }

      const count = (m) => rows.filter(r => r.met === m).length;
      // Guardrail 8: counts only, never the brief or the requirements.
      console.log('[ask:brief]', JSON.stringify({
        asker, requirements: rows.length, met: count('met'), partial: count('partial'), not_met: count('not met'), splitter,
      }));

      return json({
        brief: { requirements: rows.length, splitter },
        rows,
        human_version: HUMAN_VERSION,
        note: NOTE + (qIgnored ? NOTE_Q_IGNORED : ''),
      });
    } catch (error) {
      console.error('[ask:brief] error:', error?.name || 'error');
      return json({ error: 'Calibration failed. Please try again later.' }, 500);
    }
  };
}

export default createCalibrateHandler();
