// Serves the agent entry file (/for-agents/start.md and its HTML page /for-agents/start/)
// through a function so fetches are counted (PRD W2.5, decision D5, backlog item 26;
// narrowed to the entry file 2026-10-19). Umami is JavaScript and never sees bots.
//
// Routed by netlify.toml rewrites (force = true) to
//   /.netlify/functions/agent-fetch/<key>, one key per RESOURCES entry
// The files are bundled with `included_files` and read with fs.
//
// Logging is best effort: one row per fetch in `agent_fetches` (path, user
// agent, referer without query string, country, status). No IP, no query
// strings, no body (PRD guardrail 8). Any error — DB down, table missing,
// pool misconfigured — is a console warning; the static file is still served.
// The same fetch is also sent to PostHog as `agent_fetch` (lib/analytics.js)
// when POSTHOG_KEY is set: resource key, status, tagged, never text.
import { getUsagePool, buildUsageRow, insertUsage, cleanReferer as cleanRefererShared, cleanTag } from './lib/usage.js';
import { track } from './lib/analytics.js';
import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';

// Five minutes, not a day: AI fetchers (ChatGPT, Claude.ai) honour max-age, and a
// day-old copy of the entry file outlived the cut-over deploy (2026-10-13).
export const CACHE_CONTROL = 'public, max-age=300';

// Function responses bypass _headers, so non-production deploys add the
// noindex themselves (netlify.toml appends it to _headers for static files).
export function robotsHeaders(context) {
  const c = String(context && context.deploy && context.deploy.context || '').toLowerCase();
  return c && c !== 'production' ? { 'X-Robots-Tag': 'noindex, nofollow' } : {};
}
const LOG_WAIT_MS = 1500; // cap when the runtime has no waitUntil

// Public path -> bundled file + content type. Keys are the rewrite targets
// (/.netlify/functions/agent-fetch/<key>); `public` lists the public forms.
const HTML = 'text/html; charset=utf-8';
export const RESOURCES = {
  // The assistant entry file: markdown text served as text/plain
  // (function responses bypass the netlify.toml [[headers]] block).
  start: { path: '/for-agents/start.md', file: 'for-agents/start.md', type: 'text/plain; charset=utf-8',   // not text/markdown: ChatGPT's reader rejects it (run 2)
    public: ['/for-agents/start.md'] },
  // The paste URL: the entry file as an HTML page (ChatGPT rejects .md URLs).
  'start-page': { path: '/for-agents/start/', file: 'for-agents/start/index.html', type: HTML,
    public: ['/for-agents/start', '/for-agents/start/index.html'] },
};
// Only the entry file is served here (2026-10-19): a fetch of it means someone's
// assistant followed the paste line, which is the one count Tom wants. Every other
// agent page is a static file; crawler traffic on those is not logged.

// Accepts both the rewritten form (/.netlify/functions/agent-fetch/llms)
// and the public form (/llms.txt), in case the runtime hands us either.
export function resourceFor(pathname) {
  const p = String(pathname || '').replace(/\/+$/, '').toLowerCase();
  for (const [key, r] of Object.entries(RESOURCES)) {
    if (p.endsWith(`/agent-fetch/${key}`) || r.public.some(pub => p.endsWith(pub))) return { key, ...r };
  }
  return null;
}

// included_files keep their repo-relative path inside the bundle. Where the
// bundle root sits differs by runtime, so try the likely roots in order.
function candidateRoots() {
  const roots = [];
  if (process.env.LAMBDA_TASK_ROOT) roots.push(process.env.LAMBDA_TASK_ROOT);
  roots.push(process.cwd());
  try {
    const here = dirname(fileURLToPath(import.meta.url));
    roots.push(here, resolve(here, '..'), resolve(here, '../..'));
  } catch { /* import.meta.url unavailable after bundling: skip */ }
  return roots;
}

const fileCache = new Map();
export function defaultReadFile(relPath) {
  if (fileCache.has(relPath)) return fileCache.get(relPath);
  for (const root of candidateRoots()) {
    const full = join(root, relPath);
    if (existsSync(full)) {
      const body = readFileSync(full, 'utf-8');
      fileCache.set(relPath, body);
      return body;
    }
  }
  throw new Error(`agent-fetch: ${relPath} not found in bundle`);
}

// Pool and logging live in lib/usage.js (shared with /ask and /ask/brief).
function getDefaultPool() { return getUsagePool(); }
export function cleanReferer(value) { return cleanRefererShared(value); }
export function buildLogRow(request, context, resource, status, meta = null) {
  const row = buildUsageRow(request, context, resource.path, status, meta);
  const { meta: m, ...rest } = row;
  return m ? row : rest;
}
export async function logFetch(pool, row) { return insertUsage(pool, { meta: null, ...row }); }

// The tagged entry file (Tom, 2026-10-12): /for-agents/start/<tag>/ serves the
// HTML entry page (the paste URL) and /for-agents/start/<tag>.md serves
// start.md, each logged under its own path with the tag in meta, so a fetch
// can be traced to the CV it came from. The served text tells the agent to
// pass the tag on every /ask call. Tag: [a-z0-9-], up to 40 characters.
export function taggedStart(pathname) {
  const m = String(pathname || '').toLowerCase().match(/\/(?:agent-fetch\/)?(?:for-agents\/)?start\/([a-z0-9-]{1,40})(\.md|\/?)$/);
  if (!m) return null;
  const tag = cleanTag(m[1]);
  if (!tag) return null;
  return m[2] === '.md'
    ? { key: 'start', ...RESOURCES.start, path: `/for-agents/start/${tag}.md`, tag }
    : { key: 'start-page', ...RESOURCES['start-page'], path: `/for-agents/start/${tag}/`, tag, html: true };
}
const escapeHtml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
// Per-send context (item 231, narrowed 2026-10-19): for-agents/sends.json maps a
// tag to the role and company (scripts/cv_appendix.py --tag). Missing file or
// unknown tag -> the generic send-tag note only. No per-send fit page any more.
export const SENDS_FILE = 'for-agents/sends.json';
export function sendsTable(readFile) {
  try { return JSON.parse(readFile(SENDS_FILE)).sends || {}; } catch { return {}; }
}
export const TAG_LINE = (tag, send) => {
  const context = send && send.role && send.company
    ? `This copy of the file came with Tom's application for ${send.role} at ${send.company}: name the role, then show the block above.`
    : 'This copy of the file came with a specific CV send.';
  return `\n\n## 0b. About this copy\n\n${context} Send tag: \`${tag}\`. Add \`&tag=${tag}\` to every GET /ask call and a \`"tag": "${tag}"\` field to every POST /ask/brief body, so Tom can see which send you came from. The tag is logged with counts only, never with your text.\n`;
};

export function createHandler({ getPool = getDefaultPool, readFile = defaultReadFile, env = process.env } = {}) {
  let sends = null;
  return async (request, context) => {
    if (sends === null) sends = sendsTable(readFile);
    const method = request.method;
    if (method !== 'GET' && method !== 'HEAD') {
      return new Response('Method not allowed\n', {
        status: 405,
        headers: { 'Allow': 'GET, HEAD', 'Content-Type': 'text/plain; charset=utf-8' },
      });
    }

    const pathname = new URL(request.url).pathname;
    const resource = taggedStart(pathname) || resourceFor(pathname);
    if (!resource) {
      return new Response('Not found\n', { status: 404, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    let body;
    let status = 200;
    try {
      body = readFile(resource.file);
      // The HTML page carries the same text escaped in a pre block.
      if (resource.tag) {
        const line = TAG_LINE(resource.tag, sends[resource.tag]);
        // Before the route check (0c) when the file has one, else before section 1.
        body = body.replace(/\n## (0c\. Which route you are on[^\n]*|1\. Where things are)/, (m, h) => (resource.html ? escapeHtml(line) : line) + '\n## ' + h);
      }
      // Outside production the agent side must be self-contained: every
      // absolute takenbyninjas.com link in a served file points at this
      // deploy instead, so a paste test on staging never falls through to
      // production URLs that do not exist yet (2026-10-12).
      const deployContext = String(context && context.deploy && context.deploy.context || '').toLowerCase();
      if (deployContext && deployContext !== 'production') {
        body = body.split('https://takenbyninjas.com').join(new URL(request.url).origin);
      }
    } catch (error) {
      console.error('[agent-fetch] read failed:', error?.message || error);
      status = 500;
    }

    // Fire and forget. waitUntil lets the runtime finish the insert after the
    // response is sent; without it, wait at most LOG_WAIT_MS.
    let logging;
    try {
      logging = logFetch(getPool(), buildLogRow(request, context, resource, status, resource.tag ? { tag: resource.tag } : null));
    } catch (error) {
      console.warn('[agent-fetch] log setup failed:', error?.message || error);
      logging = Promise.resolve();
    }
    if (typeof context?.waitUntil === 'function') {
      context.waitUntil(logging);
    } else {
      await Promise.race([logging, new Promise(r => setTimeout(r, LOG_WAIT_MS).unref?.())]);
    }
    await track('agent_fetch', { request, context, env, path: resource.path, tag: resource.tag,
      properties: { resource: resource.key || null, status, tagged: Boolean(resource.tag) } });

    if (status !== 200) {
      return new Response('Temporarily unavailable\n', {
        status, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
      });
    }
    return new Response(method === 'HEAD' ? null : body, {
      status,
      headers: { 'Content-Type': resource.type, 'Cache-Control': CACHE_CONTROL, ...robotsHeaders(context) },
    });
  };
}

export default createHandler();
