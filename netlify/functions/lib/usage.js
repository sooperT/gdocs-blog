// Usage logging for the agent side (PRD W2.5, D5; Tom 2026-10-12: "how do we
// track if anyone uses it"). One table, agent_fetches, for page fetches and
// for /ask and /ask/brief calls: path, user agent, referer (no query string),
// country, status, and `meta` (JSONB): counts, role shape, asker, and the
// send tag, never query text or brief text (guardrail 8). Best effort: any
// failure is a console warning; a table without the meta column (created
// before 2026-10-12) still gets the row without meta.
import pg from 'pg';

export const TAG_RE = /^[a-z0-9][a-z0-9-]{0,39}$/;
export function cleanTag(value) {
  const t = String(value || '').trim().toLowerCase();
  return TAG_RE.test(t) ? t : null;
}

let defaultPool = null;
export function getUsagePool(env = process.env) {
  if (!env.NILEDB_URL) return null;
  if (!defaultPool) {
    defaultPool = new pg.Pool({ connectionString: env.NILEDB_URL, ssl: { rejectUnauthorized: false }, connectionTimeoutMillis: 3000, max: 2 });
    defaultPool.on('error', (e) => console.warn('[usage] pool error:', e.message));
  }
  return defaultPool;
}

export function cleanReferer(value) {
  if (!value) return null;
  try { const u = new URL(value); return (u.origin + u.pathname).slice(0, 512); } catch { return null; }
}

export function buildUsageRow(request, context, path, status, meta = null) {
  const h = request.headers;
  const country = h.get('x-country') || context?.geo?.country?.code || null;
  return {
    path: String(path).slice(0, 512),
    user_agent: (h.get('user-agent') || '').slice(0, 512),
    referer: cleanReferer(h.get('referer')),
    country: country ? String(country).slice(0, 8) : null,
    status,
    meta: meta && typeof meta === 'object' ? meta : null,
  };
}

const UNDEFINED_COLUMN = '42703';
export async function insertUsage(pool, row) {
  try {
    if (!pool) throw new Error('NILEDB_URL not set');
    try {
      await pool.query(
        'INSERT INTO agent_fetches (path, user_agent, referer, country, status, meta) VALUES ($1, $2, $3, $4, $5, $6)',
        [row.path, row.user_agent, row.referer, row.country, row.status, row.meta ? JSON.stringify(row.meta) : null],
      );
    } catch (error) {
      if (error?.code !== UNDEFINED_COLUMN) throw error;
      await pool.query(
        'INSERT INTO agent_fetches (path, user_agent, referer, country, status) VALUES ($1, $2, $3, $4, $5)',
        [row.path, row.user_agent, row.referer, row.country, row.status],
      );
    }
  } catch (error) {
    console.warn('[usage] log failed:', error?.message || error);
  }
}

const LOG_WAIT_MS = 1500;
// Fire and forget: waitUntil when the runtime has it, else wait at most LOG_WAIT_MS.
export async function logUsage({ pool, request, context, path, status, meta }) {
  let logging;
  try {
    logging = insertUsage(pool, buildUsageRow(request, context, path, status, meta));
  } catch (error) {
    console.warn('[usage] log setup failed:', error?.message || error);
    return;
  }
  if (typeof context?.waitUntil === 'function') context.waitUntil(logging);
  else await Promise.race([logging, new Promise(r => setTimeout(r, LOG_WAIT_MS).unref?.())]);
}
