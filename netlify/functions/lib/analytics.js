// PostHog event capture for the agent side (Tom, 2026-10-13: "see whether
// people's agents use the agent side"). Three events, one per function:
// agent_fetch (agent-fetch.js), agent_ask (ask.js), agent_brief (calibrate.js).
// Server side only: the callers are bots, so no JavaScript snippet ever runs.
//
// Best effort, never blocking: no POSTHOG_KEY means no fetch at all; a key
// means one POST to PostHog's capture endpoint with a 1,500 ms abort, every
// error swallowed to one console.warn that never carries the payload.
//
// Privacy (PRD guardrail 8, same line as lib/usage.js): properties carry
// counts, fixed-list labels, section ids, the send tag and the deploy env.
// Never the IP, never the raw user agent (bot family and the first product
// token only), never a query string, never a question, brief or evidence
// text, never the referer path (host only).
//
// distinct_id: the send tag when the call carries one (one id per CV send,
// so a send's fetches and asks line up in PostHog). Otherwise a keyed hash:
// HMAC-SHA256(POSTHOG_SALT or the key, "<utc date>:<client ip>") cut to 16
// hex characters. The date in the input rotates the id every UTC day, so a
// visitor can be counted as one within a day but is never identifiable and
// never followable across days; without the salt the hash cannot be
// reversed or rebuilt from an IP. The IP itself is never sent.
import { createHmac } from 'node:crypto';
import { clientIp } from './guard.js';
import { cleanTag } from './usage.js';
import { resolveTombotEnv } from './db_env.js';

export const DEFAULT_HOST = 'https://eu.i.posthog.com';
export const CAPTURE_PATH = '/i/v0/e/';
export const CAPTURE_TIMEOUT_MS = 1500;
export const UA_PRODUCT_MAX = 40;

// Same table and order as scripts/live_report.py BOT_FAMILIES: first match
// wins, internal probes and shell clients before the catch-alls. Keep the
// two in step so PostHog and the live report name the same families.
export const BOT_FAMILIES = [
  ['OpenAI', /GPTBot|ChatGPT-User|OAI-SearchBot/i],
  ['Anthropic', /ClaudeBot|Claude-User|Claude-SearchBot|anthropic/i],
  ['Perplexity', /PerplexityBot|Perplexity-User/i],
  ['Google', /Google-Extended|Googlebot|GoogleOther/i],
  ['Microsoft', /bingbot|Copilot|BingPreview|msnbot/i],
  ['Apple', /Applebot/i],
  ['Meta', /meta-externalagent|facebookexternalhit/i],
  ['Amazon', /Amazonbot/i],
  ['ByteDance', /Bytespider/i],
  ['CommonCrawl', /CCBot/i],
  ['DuckDuckGo', /DuckAssistBot|DuckDuckBot/i],
  ['internal (tbn-*)', /^tbn-/i],
  ['curl', /^curl\//i],
  ['python', /python-requests|python-urllib|aiohttp|httpx/i],
  ['other bot', /bot|crawler|spider|fetch/i],
  ['browser', /Mozilla\//i],
];

export function botFamily(userAgent) {
  const ua = String(userAgent || '');
  if (!ua) return '(empty)';
  for (const [name, re] of BOT_FAMILIES) if (re.test(ua)) return name;
  return 'other';
}

// First product token, version dropped, IPv4 redacted, at most 40 characters.
const IPV4_RE = /\d{1,3}(?:\.\d{1,3}){3}/g;
export function uaProduct(userAgent) {
  const token = String(userAgent || '').trim().split(/\s+/, 1)[0] || '';
  return token.split('/')[0].replace(IPV4_RE, '[ip]').slice(0, UA_PRODUCT_MAX) || null;
}

export function refererHost(value) {
  if (!value) return null;
  try { return new URL(value).hostname.toLowerCase().slice(0, 253) || null; } catch { return null; }
}

// Fixed-list buckets, as live_report.py asker_bucket: never the raw value.
export const ASKERS = ['recruiter-agent', 'hiring-manager', 'human'];
export function askerBucket(value) {
  if (!value) return '(none)';
  return ASKERS.includes(String(value)) ? String(value) : 'other';
}

export function utcDay(now = new Date()) {
  return now.toISOString().slice(0, 10);
}

// The keyed, daily-rotating visitor id described in the header.
export function hashedVisitor(ip, salt, now = new Date()) {
  return createHmac('sha256', String(salt)).update(`${utcDay(now)}:${ip || 'unknown'}`).digest('hex').slice(0, 16);
}

export function distinctIdFor({ request, tag, env = process.env, now = new Date() }) {
  const t = cleanTag(tag);
  if (t) return t;
  const salt = env.POSTHOG_SALT || env.POSTHOG_KEY;
  return hashedVisitor(request ? clientIp(request) : 'unknown', salt, now);
}

function pathOf(request) {
  try { return new URL(request.url).pathname.slice(0, 512); } catch { return null; }
}

// The properties every event carries, before the per-event ones.
export function baseProperties({ request, context, env = process.env, path, tag }) {
  const h = request?.headers;
  const ua = h ? h.get('user-agent') : '';
  return {
    env: resolveTombotEnv(env, context?.deploy?.context),
    site: 'takenbyninjas',   // one PostHog project may hold several sites
    path: path != null ? String(path).slice(0, 512) : (request ? pathOf(request) : null),
    bot_family: botFamily(ua),
    ua_product: uaProduct(ua),
    referer_host: refererHost(h ? h.get('referer') : null),
    tag: cleanTag(tag),
  };
}

// Sends one event. Resolves (never rejects) once PostHog has answered, the
// timeout has fired, or at once when there is no key. `fetch` is injectable
// for tests; the default is read at call time so a test's globalThis.fetch
// replacement is honoured.
export async function capture(event, { request, context, env = process.env, distinctId, properties = {}, path, tag, fetch: fetchImpl, now } = {}) {
  const key = String(env.POSTHOG_KEY || '').trim();
  if (!key) return false;
  const doFetch = fetchImpl || globalThis.fetch;
  if (typeof doFetch !== 'function') return false;
  const host = String(env.POSTHOG_HOST || DEFAULT_HOST).trim().replace(/\/+$/, '');
  const when = now || new Date();
  const base = baseProperties({ request, context, env, path, tag });
  const body = {
    api_key: key,
    event: String(event),
    distinct_id: distinctId || distinctIdFor({ request, tag, env, now: when }),
    properties: { ...properties, ...base },
    timestamp: when.toISOString(),
  };
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), CAPTURE_TIMEOUT_MS);
  timer.unref?.();
  try {
    const res = await doFetch(host + CAPTURE_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ac.signal,
    });
    if (res && res.ok === false) console.warn('[analytics] capture refused:', res.status);
    return Boolean(res && res.ok !== false);
  } catch (error) {
    console.warn('[analytics] capture failed:', error?.name || 'error');
    return false;
  } finally {
    clearTimeout(timer);
  }
}

// Fire after the response is built: waitUntil when the runtime has it, else
// await (capture itself never takes longer than CAPTURE_TIMEOUT_MS). Same
// pattern as logUsage in lib/usage.js.
export async function track(event, opts = {}) {
  let p;
  try { p = capture(event, opts); } catch (error) { console.warn('[analytics] setup failed:', error?.name || 'error'); return; }
  if (typeof opts.context?.waitUntil === 'function') opts.context.waitUntil(p);
  else await p;
}
