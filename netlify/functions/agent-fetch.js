// Serves /about/agent/ and /llms.txt through a function so crawler fetches
// are counted (PRD W2.5, decision D5). Umami is JavaScript and never sees bots.
//
// Routed by netlify.toml rewrites (force = true) to
//   /.netlify/functions/agent-fetch/page  and  /.netlify/functions/agent-fetch/llms
// The files are bundled with `included_files` and read with fs.
//
// Logging is best effort: one row per fetch in `agent_fetches` (path, user
// agent, referer without query string, country, status). No IP, no query
// strings, no body (PRD guardrail 8). Any error — DB down, table missing,
// pool misconfigured — is a console warning; the static file is still served.
import pg from 'pg';
import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';

export const CACHE_CONTROL = 'public, max-age=86400';
const LOG_WAIT_MS = 1500; // cap when the runtime has no waitUntil

// Public path -> bundled file + content type.
export const RESOURCES = {
  page: { path: '/about/agent/', file: 'about/agent/index.html', type: 'text/html; charset=utf-8' },
  llms: { path: '/llms.txt', file: 'llms.txt', type: 'text/plain; charset=utf-8' },
};

// Accepts both the rewritten form (/.netlify/functions/agent-fetch/llms)
// and the public form (/llms.txt), in case the runtime hands us either.
export function resourceFor(pathname) {
  const p = String(pathname || '').replace(/\/+$/, '').toLowerCase();
  if (p.endsWith('/llms') || p.endsWith('/llms.txt')) return RESOURCES.llms;
  if (p.endsWith('/page') || p.endsWith('/about/agent') || p.endsWith('/about/agent/index.html')) return RESOURCES.page;
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

let defaultPool = null;
function getDefaultPool() {
  if (!process.env.NILEDB_URL) return null;
  if (!defaultPool) {
    defaultPool = new pg.Pool({
      connectionString: process.env.NILEDB_URL,
      ssl: { rejectUnauthorized: false },
      connectionTimeoutMillis: 3000,
      max: 2,
    });
    // An idle-client error must never crash the function.
    defaultPool.on('error', (e) => console.warn('[agent-fetch] pool error:', e.message));
  }
  return defaultPool;
}

// Referer without query string or fragment; null when absent or unparseable.
export function cleanReferer(value) {
  if (!value) return null;
  try {
    const u = new URL(value);
    return (u.origin + u.pathname).slice(0, 512);
  } catch {
    return null;
  }
}

export function buildLogRow(request, context, resource, status) {
  const h = request.headers;
  const country = h.get('x-country') || context?.geo?.country?.code || null;
  return {
    path: resource.path,
    user_agent: (h.get('user-agent') || '').slice(0, 512),
    referer: cleanReferer(h.get('referer')),
    country: country ? String(country).slice(0, 8) : null,
    status,
  };
}

export async function logFetch(pool, row) {
  try {
    if (!pool) throw new Error('NILEDB_URL not set');
    await pool.query(
      'INSERT INTO agent_fetches (path, user_agent, referer, country, status) VALUES ($1, $2, $3, $4, $5)',
      [row.path, row.user_agent, row.referer, row.country, row.status],
    );
  } catch (error) {
    console.warn('[agent-fetch] log failed:', error?.message || error);
  }
}

export function createHandler({ getPool = getDefaultPool, readFile = defaultReadFile } = {}) {
  return async (request, context) => {
    const method = request.method;
    if (method !== 'GET' && method !== 'HEAD') {
      return new Response('Method not allowed\n', {
        status: 405,
        headers: { 'Allow': 'GET, HEAD', 'Content-Type': 'text/plain; charset=utf-8' },
      });
    }

    const resource = resourceFor(new URL(request.url).pathname);
    if (!resource) {
      return new Response('Not found\n', { status: 404, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    let body;
    let status = 200;
    try {
      body = readFile(resource.file);
    } catch (error) {
      console.error('[agent-fetch] read failed:', error?.message || error);
      status = 500;
    }

    // Fire and forget. waitUntil lets the runtime finish the insert after the
    // response is sent; without it, wait at most LOG_WAIT_MS.
    let logging;
    try {
      logging = logFetch(getPool(), buildLogRow(request, context, resource, status));
    } catch (error) {
      console.warn('[agent-fetch] log setup failed:', error?.message || error);
      logging = Promise.resolve();
    }
    if (typeof context?.waitUntil === 'function') {
      context.waitUntil(logging);
    } else {
      await Promise.race([logging, new Promise(r => setTimeout(r, LOG_WAIT_MS).unref?.())]);
    }

    if (status !== 200) {
      return new Response('Temporarily unavailable\n', {
        status, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
      });
    }
    return new Response(method === 'HEAD' ? null : body, {
      status,
      headers: { 'Content-Type': resource.type, 'Cache-Control': CACHE_CONTROL },
    });
  };
}

export default createHandler();
