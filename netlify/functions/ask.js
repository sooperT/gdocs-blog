// GET /ask?q=...&asker=...  —  TomBot made fetchable (PRD W3, slice 1),
// agent retrieval profile (PRD section 5, backlog item 20).
// Retrieval only: up to 5 matched TomBot sections verbatim, each with its id
// as provenance and its score. No Claude call, no generated text, no guessing
// below the shared match threshold. Routed from /ask by netlify.toml.
// GET /ask with no q and no brief returns the map (every section id and the
// questions that route to it).
// GET /ask?brief=... is brief calibration (W4) and is handed to calibrate.js;
// POST briefs go to /ask/brief.
// Guardrails (switch-off, rate limit, deny-list, schema, map) live in
// lib/guard.js; the database/environment rule lives in lib/db_env.js.
import { envForRequest } from './lib/db_env.js';
import { retrieve as defaultRetrieve, listSections as defaultListSections, prepareAgentQuery } from './lib/retrieval.js';
import { isDbEnvError } from './lib/db_env.js';
import { strengthFor } from './lib/strength.js';
import { classifyKnockouts, answerFor, FACT_NOTE, NOT_STATED_NOTE } from './lib/facts.js';
import { referencesFor } from './lib/references.js';
import { logUsage, getUsagePool, cleanTag } from './lib/usage.js';
import {
  agentSideEnabled, AGENT_OFF_ERROR, createRateLimiter, createSectionMap,
  applyDenyList, validateRows, dropUnknownSections, omitAgentLines, AGENT_HIDDEN_SECTIONS,
  checkQuestionLength, isInjectionLine,
} from './lib/guard.js';
import { createCalibrateHandler } from './calibrate.js';

export const HUMAN_VERSION = 'https://takenbyninjas.com/projects/tombot/';
export const AGENT_TOP_K = 5;
const MAP_ROUTES = 3;
const USAGE = 'Usage: GET /ask for the map of sections. GET /ask?q=<your question>&asker=<optional: recruiter-agent | hiring-manager | human>. For a job brief: GET /ask?brief=<brief>, or POST it to /ask/brief.';

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

// `**Direct answers:**` block (PRD D2): the bold label followed by a
// markdown list. Returns { rest, lines } with the block removed from rest;
// lines is null when the content has no such block.
const DIRECT_ANSWERS = /\*\*Direct answers:\*\*[ \t]*\n((?:[ \t]*[-*][^\n]*(?:\n|$))+)/;
export function extractDirectAnswers(content) {
  const text = String(content || '');
  const m = text.match(DIRECT_ANSWERS);
  if (!m) return { rest: text, lines: null };
  const lines = m[1].split('\n')
    .map(l => stripMarkers(l.replace(/^\s*[-*]\s*/, '')).trim())
    .filter(Boolean);
  return { rest: text.replace(m[0], '\n'), lines };
}

const stripMarkers = (t) => t.replace(/\[[A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)*\]/g, '');

// DB content is already parsed (no Questions / follow-ups blocks), but strip
// them defensively, plus HTML comments, the Direct answers block (returned
// separately) and inline [SECTION.ID] routing markers.
// The prose itself is untouched.
export function cleanAnswer(content) {
  let text = extractDirectAnswers(content).rest;
  text = text.replace(/<!--[\s\S]*?-->/g, '');
  text = text.replace(/\*\*Questions that route here:\*\*[ \t]*\n(?:[ \t]*-[^\n]*\n?)*/g, '');
  text = text.replace(/\*\*Suggested follow-ups:\*\*[\s\S]*$/g, '');
  text = stripMarkers(text);
  text = omitAgentLines(text).replace(/\n{3,}/g, '\n\n');
  return text.trim();
}

// Year only when the text states one plainly: an explicit range in the
// opening line ("Mar 2020 - Feb 2022" -> "2020-2022", "2016-present"),
// else the single distinct year in the whole answer. Tables, or several
// unrelated years with no opening range -> null.
export function deriveYear(answer) {
  if (!answer) return null;
  const first = answer.split('\n')[0];
  const range = first.includes('|') ? null
    : first.match(/\b((?:19|20)\d{2})\b[^\n\d]{0,12}?[-–—][^\n\d]{0,12}?\b((?:19|20)\d{2}|present)\b/i);
  if (range) {
    const end = range[2].toLowerCase();
    return end === range[1] ? range[1] : `${range[1]}-${end}`;
  }
  const years = [...new Set(answer.match(/\b(?:19|20)\d{2}\b/g) || [])];
  return years.length === 1 ? years[0] : null;
}

// Strength (Led / Contributed) comes from the shared label table
// (lib/strength.json), never inferred from prose: labelled sections carry
// their label, every other section null.
export function deriveStrength(match) {
  return strengthFor(match?.title);
}

// Evidence tiers (PRD W1b). Every row's own answer/evidence is TomBot content,
// Tom's own account: self-reported. LinkedIn recommendations are references
// for the period a section belongs to (R1012-15), never quoted against a
// claim: `references` on a row is {period, count, url, tier, note} or null.
export const SELF_REPORTED = 'self-reported';
export const ATTESTED = 'attested';
export const LINKEDIN_RECORD = 'https://www.linkedin.com/in/tomstenson/details/recommendations/';

const parseJsonList = (v) => {
  let list = v;
  if (typeof list === 'string') {
    try { list = JSON.parse(list); } catch { list = null; }
  }
  return Array.isArray(list) ? list : null;
};

// direct_answers: the column when the loader filled it, else the
// `**Direct answers:**` block parsed out of the text (older loads), else null.
function directAnswerLines(match) {
  const column = parseJsonList(match.direct_answers);
  if (column && column.length) {
    return column.filter(l => typeof l === 'string').map(l => stripMarkers(l).trim()).filter(Boolean);
  }
  return extractDirectAnswers(match.content).lines;
}

export function followUpTexts(followUps) {
  let list = followUps;
  if (typeof list === 'string') {
    try { list = JSON.parse(list); } catch { list = []; }
  }
  if (!Array.isArray(list)) return [];
  return list
    .filter(f => !(f && typeof f === 'object' && AGENT_HIDDEN_SECTIONS.has(f.target)))   // no chip into a hidden section
    .map(f => (typeof f === 'string' ? f : f?.text))
    .filter(t => typeof t === 'string' && t.length > 0);
}

const roundScore = (x) => Math.round(Number(x) * 100) / 100;

// One retrieved chunk row -> one outgoing match (deny-list applied).
// Returns { row, withheld }.
export function buildMatch(match) {
  const direct = directAnswerLines(match);
  const denied = applyDenyList(cleanAnswer(match.content));
  let withheld = denied.withheld;
  const directAnswers = direct ? direct.map(l => { const d = applyDenyList(l); withheld += d.withheld; return d.text; }) : null;
  return {
    withheld,
    row: {
      section: match.title,
      answer: denied.text,
      source: `TomBot ${match.title}`,
      tier: SELF_REPORTED,
      year: deriveYear(denied.text),
      strength: deriveStrength(match),
      score: roundScore(match.similarity),
      direct_answers: directAnswers,
      references: referencesFor(match.title),
    },
  };
}

// A question a screener decides yes or no (location, right to work, start
// date, salary) also gets the screening fact, so "When can he start?" answers
// "on request" instead of nothing. Null when the question asks no such fact.
export function factsFor(q) {
  const facts = classifyKnockouts(q).map(f => {
    const answer = answerFor(q, f);
    return { fact_type: f.type, label: f.label, answer, section: answer ? f.section : null, note: answer ? FACT_NOTE : NOT_STATED_NOTE };
  });
  return facts.length ? facts : null;
}

function unavailable(error, tag) {
  if (isDbEnvError(error)) {
    console.error(tag, error.message);
    return json({ error: error.message, human_version: HUMAN_VERSION }, 503);
  }
  console.error(tag, 'retrieval error:', error?.name || error || 'error');
  return json({ error: 'Retrieval is unavailable right now. Please try again later.', human_version: HUMAN_VERSION }, 503);
}

export function createHandler({
  retrieve = defaultRetrieve,
  listSections,
  calibrate,
  env = process.env,
  limiter = createRateLimiter(),
  sectionMap,
  usagePool,   // test seam; default: the shared pool when NILEDB_URL is set
} = {}) {
  let runEnv = env;   // pinned per request from the runtime deploy context (db_env.envForRequest)
  const map = sectionMap || createSectionMap({ listSections: listSections || (() => defaultListSections({ env: runEnv })) });
  let calibrateHandler = calibrate || null;
  return async (request, context) => {
    runEnv = envForRequest(env, context);
    if (!agentSideEnabled(runEnv)) return json({ error: AGENT_OFF_ERROR }, 503);
    if (request.method !== 'GET') {
      return json({ error: 'Method not allowed. ' + USAGE }, 405, { 'Allow': 'GET' });
    }
    if (limiter) {
      const rl = limiter.check(request);
      if (!rl.ok) return json({ error: 'Too many requests. Try again shortly.' }, 429, { 'Retry-After': String(rl.retryAfter) });
    }

    const url = new URL(request.url);
    if (url.searchParams.has('brief')) {
      // Created lazily: calibrate.js imports helpers from this module.
      // Rate limit already counted here, so the delegate does not count again.
      calibrateHandler = calibrateHandler || createCalibrateHandler({ retrieve, env, limiter: null, sectionMap: map, usagePool });
      return calibrateHandler(request, context);
    }
    const q = (url.searchParams.get('q') || '').trim();
    const asker = url.searchParams.get('asker') || null;
    const tag = cleanTag(url.searchParams.get('tag'));

    if (!q) {
      // The map: every section id and the first questions that route to it.
      try {
        const { sections } = await map.get();
        return json({
          sections: sections.map(s => ({ id: s.id, routes: (s.questions || []).slice(0, MAP_ROUTES) })),
          count: sections.length,
          human_version: HUMAN_VERSION,
          usage: USAGE,
        });
      } catch (error) {
        return unavailable(error, '[ask:map]');
      }
    }

    // Guard before anything is embedded (P-1012-8): a question over the cap
    // is 414; a question that reads as an instruction is answered null with
    // a flag and never echoed. Neither spends a Voyage call.
    const tooLong = checkQuestionLength(q);
    if (tooLong) return json({ error: tooLong.error, usage: USAGE }, tooLong.status);
    if (isInjectionLine(q)) {
      console.log('[guard]', JSON.stringify({ rule: 'injection_pattern', lines: 1, path: '/ask' }));
      const usage = { asker, tag, query_length: q.length, section: null, matches: 0, withheld: 0, flags: ['injection_pattern'] };
      await logUsage({ pool: usagePool === undefined ? getUsagePool(runEnv) : usagePool, request, context, path: '/ask', status: 200, meta: usage });
      return json({ answer: null, reason: 'the question reads as an instruction, not a question about Tom', flags: ['injection_pattern'], matches: [], human_version: HUMAN_VERSION });
    }

    let result, ids;
    try {
      result = await retrieve(q, { topK: AGENT_TOP_K, env: runEnv, prepare: prepareAgentQuery, exclude: AGENT_HIDDEN_SECTIONS });
      if (result?.error) return unavailable(result.error, '[ask]');
      ({ ids } = await map.get());
    } catch (error) {
      return unavailable(error, '[ask]');
    }

    try {
      const raw = Array.isArray(result.matches) ? result.matches : (result.match ? [result.match] : []);
      let withheld = 0;
      const built = raw.slice(0, AGENT_TOP_K).map(m => { const b = buildMatch(m); withheld += b.withheld; return { row: b.row, match: m }; });
      const known = dropUnknownSections(built.map(b => b.row), ids).rows;
      const { rows } = validateRows(known, { tag: '[ask]' });
      const usage = { asker, tag, query_length: q.length, section: rows[0]?.section || null, matches: rows.length, withheld };
      console.log('[ask]', JSON.stringify(usage));
      await logUsage({ pool: usagePool === undefined ? getUsagePool(runEnv) : usagePool, request, context, path: '/ask', status: 200, meta: usage });

      if (!rows.length) {
        return json({ answer: null, reason: 'no matching content', matches: [], facts: factsFor(q), human_version: HUMAN_VERSION });
      }

      const best = rows[0];
      const bestMatch = built.find(b => b.row === best).match;
      return json({
        answer: best.answer,
        section: best.section,
        source: best.source,
        tier: best.tier,
        strength: best.strength,
        year: best.year,
        direct_answers: best.direct_answers,
        references: best.references,
        follow_ups: followUpTexts(bestMatch.follow_ups),
        score: best.score,
        matches: rows,
        facts: factsFor(q),
        withheld,
        human_version: HUMAN_VERSION,
      });
    } catch (error) {
      console.error('[ask] error:', error?.name || 'error');
      return json({ error: 'Retrieval failed. Please try again later.' }, 500);
    }
  };
}

export default createHandler();

// Netlify-side limit, aggregated across instances (P-1011-1): same numbers as
// chat.js and the in-memory floor in lib/guard.js. No `path`: routing stays in
// netlify.toml.
export const config = {
  rateLimit: { windowLimit: 20, windowSize: 60, aggregateBy: ['ip'], action: 'rate_limit' },
};
