// Which database may this deploy talk to? (PRD v3 section 8, item 17.)
// Same hard rule as scripts/db_target.py: staging database names must
// contain "staging", the production database must be named "niledb".
// A mismatch throws a one-line DbEnvError (no stack shown to callers, never
// the URL) so /ask and calibration answer 503 instead of connecting.
// No operator confirmation anywhere.

export const PRODUCTION_DB_NAME = 'niledb';

export class DbEnvError extends Error {
  constructor(message) {
    super(message);
    this.name = 'DbEnvError';
    this.code = 'DB_ENV';
  }
}

export const isDbEnvError = (e) => Boolean(e) && (e instanceof DbEnvError || e.code === 'DB_ENV');

// TOMBOT_ENV wins (set per context in netlify.toml). Fallback: Netlify's
// CONTEXT. Neither set: production, so local `netlify dev` against .env
// keeps working as before.
export function resolveTombotEnv(env = process.env) {
  const explicit = String(env.TOMBOT_ENV || '').trim().toLowerCase();
  if (explicit) return explicit;
  const context = String(env.CONTEXT || '').trim().toLowerCase();
  if (context === 'production') return 'production';
  if (['branch-deploy', 'deploy-preview', 'dev'].includes(context)) return 'staging';
  return 'production';
}

// Database name from a postgres URL: the path after the host, without the
// leading slash or any query string. null when unparseable.
export function dbNameFromUrl(url) {
  try {
    const name = decodeURIComponent(new URL(String(url)).pathname.replace(/^\/+/, ''));
    return name || null;
  } catch {
    return null;
  }
}

// Returns the connection string to use, or throws DbEnvError.
export function resolveDbUrl(env = process.env) {
  const tombotEnv = resolveTombotEnv(env);
  const url = env.NILEDB_URL;
  if (!url) throw new DbEnvError(`database refused: NILEDB_URL is not set (${tombotEnv})`);
  const name = dbNameFromUrl(url);
  if (!name) throw new DbEnvError(`database refused: NILEDB_URL has no database name (${tombotEnv})`);
  if (tombotEnv === 'staging') {
    if (!name.toLowerCase().includes('staging')) {
      throw new DbEnvError('database refused: staging must use a database whose name contains "staging"');
    }
  } else if (tombotEnv === 'production') {
    if (name !== PRODUCTION_DB_NAME) {
      throw new DbEnvError(`database refused: production must use the database named "${PRODUCTION_DB_NAME}"`);
    }
  } else {
    throw new DbEnvError(`database refused: unknown TOMBOT_ENV "${tombotEnv.slice(0, 20)}"`);
  }
  return url;
}
