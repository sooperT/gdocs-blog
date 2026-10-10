// GET /ask?q=...&asker=...  —  TomBot made fetchable (PRD W3, slice 1).
// Retrieval only: returns the matched TomBot section verbatim, with its id
// as provenance. No Claude call, no generated text, no guessing below the
// match threshold. Routed from /ask by netlify.toml.
import { retrieve as defaultRetrieve } from './lib/retrieval.js';

const HUMAN_VERSION = '/projects/tombot/';
const USAGE = 'Usage: GET /ask?q=<your question>&asker=<optional: recruiter-agent | hiring-manager | human>';

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

// DB content is already parsed (no Questions / follow-ups blocks), but strip
// them defensively, plus HTML comments and inline [SECTION.ID] routing markers.
// The prose itself is untouched.
export function cleanAnswer(content) {
  let text = String(content || '');
  text = text.replace(/<!--[\s\S]*?-->/g, '');
  text = text.replace(/\*\*Questions that route here:\*\*[ \t]*\n(?:[ \t]*-[^\n]*\n?)*/g, '');
  text = text.replace(/\*\*Suggested follow-ups:\*\*[\s\S]*$/g, '');
  text = text.replace(/\[[A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)*\]/g, '');
  text = text.replace(/\n{3,}/g, '\n\n');
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

// Strength (Led / Contributed) is not a field in TomBot content yet, and
// inferring it from prose would be a guess. Null until the content carries it.
export function deriveStrength(/* section */) {
  return null;
}

export function followUpTexts(followUps) {
  let list = followUps;
  if (typeof list === 'string') {
    try { list = JSON.parse(list); } catch { list = []; }
  }
  if (!Array.isArray(list)) return [];
  return list
    .map(f => (typeof f === 'string' ? f : f?.text))
    .filter(t => typeof t === 'string' && t.length > 0);
}

export function createHandler({ retrieve = defaultRetrieve } = {}) {
  return async (request) => {
    if (request.method !== 'GET') {
      return json({ error: 'Method not allowed. ' + USAGE }, 405, { 'Allow': 'GET' });
    }

    const url = new URL(request.url);
    const q = (url.searchParams.get('q') || '').trim();
    const asker = url.searchParams.get('asker') || null;

    if (!q) {
      return json({ error: 'Missing required parameter q.', usage: USAGE }, 400);
    }

    try {
      const { match, error } = await retrieve(q);
      if (error) {
        console.error('[ask] retrieval error:', error);
        return json({ error: 'Retrieval is unavailable right now. Please try again later.', human_version: HUMAN_VERSION }, 503);
      }
      console.log('[ask]', JSON.stringify({ asker, query_length: q.length, section: match?.title || null }));

      if (!match) {
        return json({ answer: null, reason: 'no matching content', human_version: HUMAN_VERSION });
      }

      const answer = cleanAnswer(match.content);
      return json({
        answer,
        section: match.title,
        source: `TomBot ${match.title}`,
        strength: deriveStrength(match),
        year: deriveYear(answer),
        follow_ups: followUpTexts(match.follow_ups),
        human_version: HUMAN_VERSION,
        score: Math.round(Number(match.similarity) * 100) / 100,
      });
    } catch (error) {
      console.error('[ask] error:', error);
      return json({ error: 'Retrieval failed. Please try again later.' }, 500);
    }
  };
}

export default createHandler();
