// Guardrails for the agent side (PRD W10.3, backlog item 23).
// Used by ask.js and calibrate.js only. Never by chat.js: TomBot chat is
// unchanged (R1012-2).
//
// Inbound: switch-off per context, per-IP rate limit, body size cap, text
// bodies only, requirement cap, injection-pattern stripping.
// Outbound: response schema validation, deny-list on answer/evidence text,
// section ids outside the map dropped.

// --- switch-off -------------------------------------------------------------

export const AGENT_OFF_ERROR = 'agent side is switched off in this environment';

// Unset means enabled. "false" or "0" (any case, trimmed) switches it off.
export function agentSideEnabled(env = process.env) {
  const v = String(env.AGENT_SIDE_ENABLED ?? '').trim().toLowerCase();
  return !(v === 'false' || v === '0');
}

// --- rate limit ---------------------------------------------------------------

export const RATE_LIMIT = 20;            // same number as chat's pending limiter
export const RATE_WINDOW_MS = 60 * 1000;

export function clientIp(request) {
  const h = request.headers;
  const nf = (h.get('x-nf-client-connection-ip') || '').trim();
  if (nf) return nf;
  const xff = (h.get('x-forwarded-for') || '').split(',')[0].trim();
  return xff || 'unknown';
}

// Sliding window per IP, in memory. NOTE: this is per function instance, so
// it is a soft limit: Netlify may run several instances, and a cold start
// resets it. A config-level rate limit in netlify.toml is the follow-up.
export function createRateLimiter({ limit = RATE_LIMIT, windowMs = RATE_WINDOW_MS, now = Date.now } = {}) {
  const hits = new Map();
  function prune(t) {
    for (const [ip, list] of hits) {
      const kept = list.filter(x => t - x < windowMs);
      if (kept.length) hits.set(ip, kept); else hits.delete(ip);
    }
  }
  return {
    // { ok: true } or { ok: false, retryAfter: seconds }
    check(request) {
      const t = now();
      if (hits.size > 5000) prune(t);
      const ip = clientIp(request);
      const list = (hits.get(ip) || []).filter(x => t - x < windowMs);
      if (list.length >= limit) {
        hits.set(ip, list);
        return { ok: false, retryAfter: Math.max(1, Math.ceil((list[0] + windowMs - t) / 1000)) };
      }
      list.push(t);
      hits.set(ip, list);
      return { ok: true };
    },
  };
}

// --- request bodies -----------------------------------------------------------

export const MAX_BODY_BYTES = 64 * 1024;

// Text bodies only: text/plain, application/json, or no content type (read
// as text). Anything else is 415. Bigger than 64 KB is 413.
// Returns { raw, kind: 'json' | 'text' } or { status, error }.
export async function readTextBody(request) {
  const declared = Number(request.headers.get('content-length'));
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) {
    return { status: 413, error: `Body is larger than ${MAX_BODY_BYTES / 1024} KB.` };
  }
  const type = (request.headers.get('content-type') || '').toLowerCase().split(';')[0].trim();
  let kind;
  if (type === 'application/json') kind = 'json';
  else if (type === '' || type === 'text/plain') kind = 'text';
  else return { status: 415, error: 'Send the brief as text/plain or application/json {"brief": "..."}.' };
  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > MAX_BODY_BYTES) {
    return { status: 413, error: `Body is larger than ${MAX_BODY_BYTES / 1024} KB.` };
  }
  return { raw, kind };
}

export const MAX_REQUIREMENTS_PER_BRIEF = 25;

// null when fine, else { status: 422, error, requirements }.
export function checkRequirementCount(n) {
  if (n <= MAX_REQUIREMENTS_PER_BRIEF) return null;
  return {
    status: 422,
    error: `Brief has ${n} requirements; the limit is ${MAX_REQUIREMENTS_PER_BRIEF}. Send the most important ones.`,
    requirements: n,
  };
}

// --- injection patterns (brief text) ----------------------------------------

export const INJECTION_PATTERNS = [
  /\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous\s+|prior\s+|above\s+|earlier\s+)?(?:instructions|prompts?|rules)\b/i,
  /\byou are now\b/i,
  /\bsystem prompt\b/i,
  /\bnew instructions\b/i,
  /\brate (?:this|the) candidate\b/i,
  /\bscore\b.*\b10\s*\/\s*10\b/i,
  // role-play markers
  /^\s*(?:system|assistant|user|developer)\s*:/i,
  /<\/?(?:system|assistant|user|instructions?)>/i,
  /\[\/?(?:INST|SYSTEM)\]/i,
  /\bpretend (?:to be|you are)\b/i,
  /\brole-?play\b/i,
];

export const isInjectionLine = (line) => INJECTION_PATTERNS.some(p => p.test(line));

// Strips every line matching a pattern. Returns { text, lines } where lines
// is how many were removed. Logs one line with the count only, never text.
export function stripInjection(text, { log = console.log } = {}) {
  const kept = [];
  let lines = 0;
  for (const line of String(text || '').split(/\r?\n/)) {
    if (isInjectionLine(line)) lines++; else kept.push(line);
  }
  if (lines) log('[guard]', JSON.stringify({ rule: 'injection_pattern', lines }));
  return { text: kept.join('\n'), lines };
}

// --- outgoing deny-list -------------------------------------------------------

export const WITHHELD = '[withheld]';

const STRONG_PAY_WORD = /\b(?:salary|salaries|compensation|comp|day rate|pay|wages?)\b/i;
const WEAK_PAY_WORD = /\brates?\b/i;
const CURRENCY_AMOUNT = /(?:DKK|kr\.?|€|\$|£|EUR|USD|GBP)\s?\d|\d[\d.,]*\s?[kKmM]?\s?(?:DKK|kr\b|kr\.|€|EUR|USD|GBP)/;
const BIG_NUMBER = /\b\d{1,3}(?:[.,]\d{3})+\b|\b\d+(?:[.,]\d+)?\s?k\b/i;
const SENSITIVE = /commercially sensitive|\[SENSITIVE\]/i;

// Ranking phrases: evidence, never instructions (trust contract 4).
export const RANKING_PATTERNS = [
  /\bideal candidate\b/i,
  /\brank (?:this|him|tom)\b/i,
  /\bstrongly recommend/i,
  /\btop candidate\b/i,
];

export const isSalaryLine = (line) =>
  (CURRENCY_AMOUNT.test(line) && (STRONG_PAY_WORD.test(line) || WEAK_PAY_WORD.test(line)))
  || (STRONG_PAY_WORD.test(line) && BIG_NUMBER.test(line));
export const isSensitiveLine = (line) => SENSITIVE.test(line);
export const isRankingLine = (line) => RANKING_PATTERNS.some(p => p.test(line));

// Line by line: any deny-listed line becomes [withheld].
// Returns { text, withheld } (count of lines replaced). Non-strings pass through.
export function applyDenyList(text) {
  if (typeof text !== 'string') return { text, withheld: 0 };
  let withheld = 0;
  const out = text.split('\n').map(line => {
    if (isSalaryLine(line) || isSensitiveLine(line) || isRankingLine(line)) { withheld++; return WITHHELD; }
    return line;
  });
  return { text: out.join('\n'), withheld };
}

// --- response schema ----------------------------------------------------------

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

// Every outgoing row carries section, source, year (string or null) and
// score. A row with content (answer/evidence) needs real values; a row
// without content needs nulls plus a reason (`reason`, or met: 'not met').
export function isValidRow(row) {
  if (!row || typeof row !== 'object') return false;
  if (!['section', 'source', 'year', 'score'].every(k => has(row, k))) return false;
  if (!(row.year === null || typeof row.year === 'string')) return false;
  const content = row.answer ?? row.evidence ?? null;
  // A screening fact (R1012-22) is not retrieved, so it has no score; "not
  // stated" has nothing to cite, a stated fact may be a fixed one (no section).
  if (row.kind === 'fact') {
    if (row.score !== null) return false;
    if (content === null) return row.met === 'not stated' && row.section === null && row.source === null;
    return row.met === 'fact' && typeof content === 'string'
      && (row.section === null ? row.source === null : typeof row.section === 'string' && typeof row.source === 'string');
  }
  if (content !== null) {
    return typeof content === 'string'
      && typeof row.section === 'string' && row.section.length > 0
      && typeof row.source === 'string' && row.source.length > 0
      && typeof row.score === 'number' && Number.isFinite(row.score);
  }
  return row.section === null && row.source === null && row.score === null
    && (typeof row.reason === 'string' || row.met === 'not met');
}

// Drops invalid rows and logs one error line with the count.
export function validateRows(rows, { log = console.error, tag = '[guard]' } = {}) {
  const valid = rows.filter(isValidRow);
  const dropped = rows.length - valid.length;
  if (dropped) log(tag, JSON.stringify({ rule: 'schema', dropped }));
  return { rows: valid, dropped };
}

// --- section map --------------------------------------------------------------

export const SECTION_MAP_TTL_MS = 10 * 60 * 1000;

// Caches listSections() per instance for 10 minutes. Failures are not
// cached (the next call retries) and are thrown to the caller.
export function createSectionMap({ listSections, ttlMs = SECTION_MAP_TTL_MS, now = Date.now } = {}) {
  let cached = null;
  let at = 0;
  return {
    async get() {
      if (cached && now() - at < ttlMs) return cached;
      const sections = await listSections();
      cached = { sections, ids: new Set(sections.map(s => s.id)) };
      at = now();
      return cached;
    },
  };
}

// Rows whose section is set but not in the map are dropped.
export function dropUnknownSections(rows, ids) {
  const kept = rows.filter(r => r.section == null || ids.has(r.section));
  return { rows: kept, dropped: rows.length - kept.length };
}
