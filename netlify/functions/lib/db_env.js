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

// Which environment is this request in? TOMBOT_ENV wins when a real runtime
// variable sets it. Otherwise the deploy context Netlify hands every function
// at runtime (context.deploy.context: production, branch-deploy,
// deploy-preview, dev). netlify.toml [context.*.environment] values and CONTEXT
// exist at build time only, so they are not trusted here (2026-10-12: the first
// staging deploy answered 503 because the function saw neither). Nothing known:
// production, so local `netlify dev` against .env keeps working as before.
export function tombotEnvForContext(deployContext) {
  const c = String(deployContext || '').trim().toLowerCase();
  if (c === 'production') return 'production';
  if (['branch-deploy', 'deploy-preview', 'dev'].includes(c)) return 'staging';
  return null;
}

export function resolveTombotEnv(env = process.env, deployContext) {
  const explicit = String(env.TOMBOT_ENV || '').trim().toLowerCase();
  if (explicit) return explicit;
  return tombotEnvForContext(deployContext) || tombotEnvForContext(env.CONTEXT) || 'production';
}

// The env a request runs with: TOMBOT_ENV pinned from the function's runtime
// deploy context, so every later resolveDbUrl(env) call agrees with it.
export function envForRequest(env = process.env, context) {
  const fromContext = tombotEnvForContext(context && context.deploy && context.deploy.context);
  if (env.TOMBOT_ENV || !fromContext) return env;
  return { ...env, TOMBOT_ENV: fromContext };
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
