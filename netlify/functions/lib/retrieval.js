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

// Normalize third-person references to first-person for better question matching
// "tell me about tom" -> "tell me about yourself"
// "where has tom worked" -> "where have you worked"
export function normalizeQuery(query) {
  let normalized = query;

  // Replace "tom" with "you" (case-insensitive, word boundary)
  normalized = normalized.replace(/\btom\b/gi, 'you');

  // Fix verb conjugations after replacement
  // "has you" -> "have you", "does you" -> "do you", "is you" -> "are you"
  normalized = normalized.replace(/\bhas you\b/gi, 'have you');
  normalized = normalized.replace(/\bdoes you\b/gi, 'do you');
  normalized = normalized.replace(/\bis you\b/gi, 'are you');
  normalized = normalized.replace(/\bwas you\b/gi, 'were you');

  // "you's" -> "your" (possessive)
  normalized = normalized.replace(/\byou's\b/gi, 'your');
  normalized = normalized.replace(/\byou's\b/gi, 'your'); // handle curly apostrophe

  // "about you" at end often sounds better as "about yourself"
  normalized = normalized.replace(/\babout you\b(?=\s*[?.!]?\s*$)/gi, 'about yourself');

  return normalized;
}

// Expand contractions for consistent matching with stored questions
// "what's" -> "what is", "how's" -> "how is", etc.
export function expandContractions(query) {
  return query
    .replace(/\bwhat's\b/gi, 'what is')
    .replace(/\bwhere's\b/gi, 'where is')
    .replace(/\bhow's\b/gi, 'how is')
    .replace(/\bwho's\b/gi, 'who is')
    .replace(/\bthat's\b/gi, 'that is')
    .replace(/\bit's\b/gi, 'it is')
    .replace(/\bthere's\b/gi, 'there is')
    .replace(/\bwhat're\b/gi, 'what are')
    .replace(/\bwho're\b/gi, 'who are')
    .replace(/\bthey're\b/gi, 'they are');
}

// Expand synonyms to boost matching for short/ambiguous queries (LSI-lite)
// Appends related terms rather than replacing
export function expandSynonyms(query) {
  const synonyms = {
    'kids': 'children family',
    'married': 'wife spouse family',
    'wife': 'married spouse family',
    'hobbies': 'interests outside work',
    'pitch': 'elevator summary introduction',
    'story': 'journey arc background career',
    'janitor': 'product janitor fixer',
    'compass': 'motivation values drives purpose'
  };

  let expanded = query;
  for (const [term, expansion] of Object.entries(synonyms)) {
    const regex = new RegExp(`\\b${term}\\b`, 'gi');
    if (regex.test(query)) {
      expanded += ` ${expansion}`;
    }
  }
  return expanded;
}

// Expand aliases in query (e.g., "Novo" -> "Novo Nordisk")
export async function expandAliases(query, { sql } = {}) {
  try {
    const db = sql || getPool();
    // Sort by alias length descending to avoid partial replacements
    const result = await db.query('SELECT alias, canonical_name FROM aliases ORDER BY LENGTH(alias) DESC');
    let expanded = query;
    for (const row of result.rows) {
      // Only replace if the canonical name isn't already present
      if (!expanded.toLowerCase().includes(row.canonical_name.toLowerCase())) {
        const regex = new RegExp(`\\b${row.alias}\\b`, 'gi');
        expanded = expanded.replace(regex, row.canonical_name);
      }
    }
    return expanded;
  } catch (error) {
    console.error('Alias expansion error:', error);
    return query;
  }
}

// Query clean-up, moved verbatim from chat.js so chat, /ask and calibration
// all embed the same prepared text. Order matters and matches chat:
// normalize -> contractions -> aliases -> synonyms.
// Returns every intermediate string so chat can keep its [RAG] log lines.
export async function prepareQuerySteps(query, { sql } = {}) {
  const normalized = normalizeQuery(query);
  const contractions = expandContractions(normalized);
  const aliases = await expandAliases(contractions, { sql });
  const synonyms = expandSynonyms(aliases);
  return { normalized, contractions, aliases, synonyms, final: synonyms };
}

// Convenience: just the final prepared string.
export async function prepareQuery(query, { sql } = {}) {
  return (await prepareQuerySteps(query, { sql })).final;
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

// Convenience: query -> prepareQuery -> embedding -> best section above threshold.
// Returns { match, topMatch } where match is the chunk row or null, and
// topMatch is the best row regardless of threshold (for logging), or null.
export async function retrieve(query, {
  fetchImpl, env, sql, sleep,
  topK = TOP_K,
  threshold = QUESTION_MATCH_THRESHOLD,
} = {}) {
  const db = sql || getPool(env);
  const prepared = await prepareQuery(query, { sql: db });
  const embedding = await embedQuery(prepared, { fetchImpl, env, sleep });
  if (!embedding) return { match: null, topMatch: null, error: 'embedding failed' };

  const rows = await matchSections(embedding, { topK, sql: db });
  const topMatch = rows[0] || null;
  const match = topMatch && topMatch.similarity >= threshold ? topMatch : null;
  return { match, topMatch };
}
