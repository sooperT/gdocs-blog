/**
 * Batch test follow-up suggestions against the database
 * Run with: node scripts/test-followups-batch.js
 */

import pg from 'pg';
import 'dotenv/config';

const pool = new pg.Pool({
  connectionString: process.env.NILEDB_URL,
  ssl: { rejectUnauthorized: false }
});

const THRESHOLD = 0.55;

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
      return getEmbedding(text);
    }
    throw new Error(`Voyage API error: ${err}`);
  }

  const data = await response.json();
  return data.data[0].embedding;
}

// Search using question embeddings (like chat.js does)
async function searchByQuestion(embedding) {
  const vectorStr = `[${embedding.join(',')}]`;

  const result = await pool.query(`
    SELECT id, title,
           1 - (question_embedding <=> $1::vector) as similarity
    FROM chunks
    WHERE question_embedding IS NOT NULL
    ORDER BY question_embedding <=> $1::vector
    LIMIT 3
  `, [vectorStr]);

  return result.rows;
}

// All new plain-text suggestions to test
const suggestions = [
  // NOVO family
  { query: "tell me about the Associate Product Director role", expectedTarget: "NOVO.R2" },
  { query: "tell me about your promotion to Associate Director", expectedTarget: "NOVO.R2" },
  { query: "tell me about your motivation", expectedTarget: "META.COMPASS" },
  { query: "Are you at Novo now?", expectedTarget: "TQ.LEAVING" },

  // LEO family
  { query: "tell me about the time you optimised the wrong thing", expectedTarget: "LEO.R1.STORY.FEELS" },
  { query: "What motivates you?", expectedTarget: "META.COMPASS" },
  { query: "Tell me about LEO", expectedTarget: "LEO" },
  { query: "How did this inform your approach at Novo", expectedTarget: "NOVO.R1.TRANSFORM" },

  // HOST family
  { query: "Whats your biggest learning from Host Europe", expectedTarget: "TQ.FAILURE.LEARNING" },

  // META family - placeholder skipped

  // THEME family
  { query: "tell me about Wegovycare", expectedTarget: "NOVO.R1" },
  { query: "tell me about LEO Innovation Lab", expectedTarget: "LEO" },
  { query: "tell me about the TREAT turnaround", expectedTarget: "LEO.R1.TURNAROUND" },
  { query: "Tell me how you changed domain search", expectedTarget: "HOST.R2.STORY.DOMAIN" },
  { query: "tell me about Opbeat", expectedTarget: "OPBEAT" },
  { query: "What's your ideal work setup?", expectedTarget: "TQ.SETUP" },
  { query: "Do you prefer being an IC or a manager", expectedTarget: "TQ.MGMT" },

  // TQ family
  { query: "tell me more about going on feels rather than numbers", expectedTarget: "LEO.R1.STORY.FEELS" },
  { query: "tell me more about knowing when to ship", expectedTarget: "TQ.FAILURE.SHIP" },
  { query: "tell me more about prioritising ideas over learnings", expectedTarget: "TQ.FAILURE.LEARNING" },
  { query: "tell me about Host Europe", expectedTarget: "HOST" },
  { query: "tell me more about this chatbot", expectedTarget: "META.BOT" },
  { query: "what kind of roles are you looking for", expectedTarget: "META.LOOKING" },
  { query: "Tell me more about your motivation", expectedTarget: "META.COMPASS" },
  { query: "what are you doing now", expectedTarget: "TQ.GAP" },
  { query: "what are you looking for", expectedTarget: "META.LOOKING" },
  { query: "what's the red thread", expectedTarget: "META.ARC" },
  { query: "Do you prefer IC or management roles?", expectedTarget: "TQ.MGMT" },
];

async function runTests() {
  console.log("=".repeat(70));
  console.log("Follow-up Suggestions Batch Test");
  console.log("=".repeat(70));
  console.log(`Testing ${suggestions.length} suggestions\n`);

  const results = { pass: [], fail: [] };

  for (let i = 0; i < suggestions.length; i++) {
    const { query, expectedTarget } = suggestions[i];
    process.stdout.write(`[${i + 1}/${suggestions.length}] "${query.substring(0, 40)}..." `);

    try {
      const embedding = await getEmbedding(query);
      const matches = await searchByQuestion(embedding);

      const topMatch = matches[0];
      const score = topMatch.similarity;
      const gotTarget = topMatch.title;

      // Check if it matches expected (allowing for partial match)
      const isCorrectTarget = gotTarget.includes(expectedTarget) || expectedTarget.includes(gotTarget);
      const aboveThreshold = score >= THRESHOLD;
      const pass = isCorrectTarget && aboveThreshold;

      if (pass) {
        console.log(`✓ ${score.toFixed(3)} → ${gotTarget}`);
        results.pass.push({ query, score, gotTarget, expectedTarget });
      } else {
        console.log(`✗ ${score.toFixed(3)} → ${gotTarget} (expected ${expectedTarget})`);
        results.fail.push({ query, score, gotTarget, expectedTarget, top3: matches });
      }

      // Rate limit: Voyage free tier is 3 RPM, so wait ~21s between requests
      if (i < suggestions.length - 1) {
        await new Promise(r => setTimeout(r, 21000));
      }
    } catch (err) {
      console.log(`✗ ERROR: ${err.message}`);
      results.fail.push({ query, error: err.message, expectedTarget });
    }
  }

  console.log("\n" + "=".repeat(70));
  console.log("SUMMARY");
  console.log("=".repeat(70));
  console.log(`Passing: ${results.pass.length}/${suggestions.length}`);
  console.log(`Failing: ${results.fail.length}/${suggestions.length}`);

  if (results.fail.length > 0) {
    console.log("\nFAILURES:");
    for (const f of results.fail) {
      console.log(`\n  "${f.query}"`);
      console.log(`    Expected: ${f.expectedTarget}`);
      if (f.error) {
        console.log(`    Error: ${f.error}`);
      } else {
        console.log(`    Got: ${f.gotTarget} (${f.score.toFixed(3)})`);
        if (f.top3) {
          console.log(`    Top 3:`);
          f.top3.forEach((m, i) => console.log(`      ${i+1}. ${m.title} (${m.similarity.toFixed(3)})`));
        }
      }
    }
  }

  await pool.end();
}

runTests().catch(console.error);
