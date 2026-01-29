/**
 * TomBot v3 Routing Validation Test
 *
 * Tests semantic matching to validate the question-to-question routing hypothesis.
 * Run with: node scripts/test-routing.js
 *
 * Requires: NILEDB_URL and VOYAGE_API_KEY environment variables
 */

import pg from 'pg';
import 'dotenv/config';

const pool = new pg.Pool({
  connectionString: process.env.NILEDB_URL,
  ssl: { rejectUnauthorized: false }
});

// Get embedding from Voyage AI
async function getEmbedding(text) {
  const response = await fetch('https://api.voyageai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.VOYAGE_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      input: [text],
      model: 'voyage-3'
    })
  });

  if (!response.ok) {
    const err = await response.text();
    if (err.includes('rate limit')) {
      console.log('  [Rate limited - waiting 25s...]');
      await new Promise(r => setTimeout(r, 25000));
      return getEmbedding(text); // Retry
    }
    console.error('Voyage API error:', err);
    return null;
  }

  const data = await response.json();
  return data.data[0].embedding;
}

// Search for similar content
async function searchContent(embedding) {
  const vectorStr = `[${embedding.join(',')}]`;

  const result = await pool.query(`
    SELECT id, title, chunk_type, company_name,
           1 - (embedding <=> $1::vector) as similarity
    FROM chunks
    ORDER BY embedding <=> $1::vector
    LIMIT 5
  `, [vectorStr]);

  return result.rows;
}

// Check tricky question match
async function checkTrickyMatch(embedding) {
  const vectorStr = `[${embedding.join(',')}]`;

  const result = await pool.query(`
    SELECT id, title,
           1 - (question_embedding <=> $1::vector) as q_similarity
    FROM chunks
    WHERE chunk_type = 'tricky_question'
      AND question_embedding IS NOT NULL
    ORDER BY question_embedding <=> $1::vector
    LIMIT 3
  `, [vectorStr]);

  return result.rows;
}

// Key test queries - smaller set for rate-limited testing
const testQueries = [
  // Tricky questions - should match well
  { query: "why are you leaving Novo", expected: "TQ: Why leaving Novo" },
  { query: "are you technical", expected: "TQ: Are you technical" },
  { query: "what's your biggest weakness", expected: "TQ: Weakness" },

  // Role queries - the problem area
  { query: "tell me about your current role", expected: "Role: R16/Novo" },
  { query: "what did you do at LEO", expected: "Role: LEO" },

  // Theme queries - cross-cutting
  { query: "tell me about your AI experience", expected: "AI content" },
  { query: "what growth experience do you have", expected: "Growth theme" },

  // Meta
  { query: "tell me about yourself", expected: "Summary" },
];

async function runTests() {
  console.log("=".repeat(80));
  console.log("TomBot v3 Routing Validation Test");
  console.log("=".repeat(80));
  console.log();

  for (const test of testQueries) {
    console.log(`Query: "${test.query}"`);
    console.log(`Expected: ${test.expected}`);
    console.log("-".repeat(60));

    // Get embedding once, use for both searches
    const embedding = await getEmbedding(test.query);
    if (!embedding) {
      console.log("  [Failed to get embedding]");
      continue;
    }

    // Check tricky question match
    const tqMatches = await checkTrickyMatch(embedding);
    if (tqMatches && tqMatches.length > 0) {
      console.log("Tricky Question matches:");
      for (const match of tqMatches) {
        const conf = match.q_similarity >= 0.85 ? "HIGH" :
                     match.q_similarity >= 0.7 ? "MEDIUM" : "LOW";
        console.log(`  [${conf}] ${match.q_similarity.toFixed(3)} - ${match.title}`);
      }
    }

    // Check content match
    const contentMatches = await searchContent(embedding);
    if (contentMatches && contentMatches.length > 0) {
      console.log("Content matches:");
      for (const match of contentMatches) {
        const conf = match.similarity >= 0.5 ? "HIGH" :
                     match.similarity >= 0.35 ? "MEDIUM" : "LOW";
        console.log(`  [${conf}] ${match.similarity.toFixed(3)} - [${match.chunk_type}] ${match.title}`);
      }
    }

    console.log();
    console.log("=".repeat(80));
    console.log();

    // Longer delay to respect rate limits (3 RPM = 20s between requests)
    console.log("  [Waiting 22s for rate limit...]");
    await new Promise(r => setTimeout(r, 22000));
  }

  await pool.end();
  console.log("Done!");
}

runTests().catch(console.error);
