// Shared TomBot retrieval: Voyage embedding + pgvector question match.
// Used by chat.js (TomBot chat) and ask.js (GET /ask). Every external
// dependency (fetch, DB client, env, sleep) is injectable so this can be
// unit tested with stubs and no network.
import pg from 'pg';

// Constants moved verbatim from chat.js — chat behaviour must not change.
export const QUESTION_MATCH_THRESHOLD = 0.55;  // Testing: lowered from 0.60 to catch borderline matches like "wegovy" (0.591)
export const TOP_K = 1;  // Single match only — prevents cross-section bleed and hallucination
export const VOYAGE_URL = 'https://api.voyageai.com/v1/embeddings';
export const VOYAGE_MODEL = 'voyage-3';

const defaultSleep = (ms) => new Promise(r => setTimeout(r, ms));

// Lazily created pool for callers that don't bring their own (ask.js).
// pg.Pool does not connect until the first query.
let defaultPool = null;
export function getPool(env = process.env) {
  if (!defaultPool) {
    defaultPool = new pg.Pool({
      connectionString: env.NILEDB_URL,
      ssl: { rejectUnauthorized: false }
    });
  }
  return defaultPool;
}

// Get embedding from Voyage AI with retry
export async function embedQuery(text, {
  fetchImpl = globalThis.fetch,
  env = process.env,
  retries = 2,
  sleep = defaultSleep,
} = {}) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    const response = await fetchImpl(VOYAGE_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.VOYAGE_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        input: [text],
        model: VOYAGE_MODEL
      })
    });

    if (response.ok) {
      const data = await response.json();
      return data.data[0].embedding;
    }

    if (response.status === 429 && attempt < retries) {
      await sleep(1000 * (attempt + 1));
      continue;
    }

    console.error('Voyage API error:', await response.text());
    return null;
  }
  return null;
}

// Primary search: match query embedding against question embeddings.
// One row per section (DISTINCT ON title), best similarity first, top N.
// `sql` is anything with pg's `query(text, params)` shape.
// `threshold` is optional: omitted = return top N regardless of score
// (chat.js filters itself so it can log the below-threshold top match).
export async function matchSections(embedding, { topK = TOP_K, threshold, sql } = {}) {
  try {
    const db = sql || getPool();
    const vectorStr = `[${embedding.join(',')}]`;
    const result = await db.query(`
      SELECT DISTINCT ON (title)
             id, title, content, chunk_type, question_text, follow_ups,
             1 - (question_embedding <=> $1::vector) as similarity
      FROM chunks
      WHERE question_embedding IS NOT NULL
      ORDER BY title, question_embedding <=> $1::vector
    `, [vectorStr]);

    // Re-sort by similarity after DISTINCT and take top N
    const sorted = result.rows.sort((a, b) => b.similarity - a.similarity);
    const top = sorted.slice(0, topK);
    return threshold === undefined ? top : top.filter(r => r.similarity >= threshold);
  } catch (error) {
    console.error('Question match search error:', error);
    return [];
  }
}

// Convenience: query -> embedding -> best section above threshold.
// Returns { match, topMatch } where match is the chunk row or null, and
// topMatch is the best row regardless of threshold (for logging), or null.
export async function retrieve(query, {
  fetchImpl, env, sql, sleep,
  topK = TOP_K,
  threshold = QUESTION_MATCH_THRESHOLD,
} = {}) {
  const embedding = await embedQuery(query, { fetchImpl, env, sleep });
  if (!embedding) return { match: null, topMatch: null, error: 'embedding failed' };

  const rows = await matchSections(embedding, { topK, sql: sql || getPool(env) });
  const topMatch = rows[0] || null;
  const match = topMatch && topMatch.similarity >= threshold ? topMatch : null;
  return { match, topMatch };
}
