/**
 * TomBot Routing Eval
 *
 * Fires paraphrased queries (never the verbatim stored variations) through the
 * REAL production retrieval path (retrieveContent in netlify/functions/chat.js,
 * including normalisation, alias and synonym expansion) and asserts the top
 * match lands on the expected section.
 *
 * Run with: node scripts/eval-routing.js
 * Requires: NILEDB_URL and VOYAGE_API_KEY (chat.js loads them from .env)
 *
 * Add cases here whenever content sections are added or rewritten.
 */

import { retrieveContent } from '../netlify/functions/chat.js';

// expected: array of acceptable section IDs (title column), or 'DEFLECT'
const CASES = [
  // --- New / changed sections (Aug 2026 positioning update) ---
  { query: 'could you join us a few days a week as a fractional PM?', expected: ['META.LOOKING', 'META.SERVICES'] },
  { query: 'do you take on contract gigs?', expected: ['META.LOOKING', 'META.SERVICES'] },
  { query: 'what sort of problems can you solve for my startup?', expected: ['META.SERVICES'] },
  { query: 'explain this product janitor thing', expected: ['META.JANITOR'] },
  { query: 'would you be open to mentoring a junior product manager?', expected: ['META.MENTORING'] },
  { query: 'does pineapple belong on a pizza?', expected: ['META.PINEAPPLE'] },
  { query: 'what do you get up to when you are not working?', expected: ['TQ.GAP', 'META.HOBBIES'] },
  { query: 'why did you finish at novo nordisk?', expected: ['TQ.LEAVING'] },
  { query: 'what topics do you cover?', expected: ['META.SUGGESTIONS'] },

  // --- Regression set (existing content) ---
  { query: 'give me your elevator pitch', expected: ['META'] },
  { query: 'can you write code yourself?', expected: ['TQ.TECHNICAL'] },
  { query: 'what is your biggest flaw?', expected: ['TQ.WEAKNESS'] },
  { query: 'what did you build at the innovation lab?', expected: ['LEO'] },
  { query: 'show me examples of growing a business', expected: ['THEME.GROWTH'] },
  { query: 'have you ever rescued a failing product?', expected: ['THEME.TURNAROUND', 'LEO.R1'] },
  { query: 'what was your job at the pharma company?', expected: ['NOVO', 'NOVO.R1', 'NOVO.R2'] },
  { query: 'which books would you recommend?', expected: ['META.BOOKS'] },
  // Categories promised by the META.SUGGESTIONS menu copy must all route
  { query: 'what did you do in web hosting?', expected: ['HOST', 'UK2'] },
  { query: 'tell me about your saas experience', expected: ['OPBEAT'] },
  { query: 'tell me about your devops experience', expected: ['OPBEAT'] },
  { query: 'tell me about your health-tech experience', expected: ['LEO'] },

  // --- Deflection: must NOT match anything ---
  { query: 'what is the capital of France?', expected: 'DEFLECT' },
  { query: 'write me a poem about the sea', expected: 'DEFLECT' },
];

let pass = 0;
let fail = 0;

for (const c of CASES) {
  const { chunks, method, topMatch } = await retrieveContent(c.query);
  const got = method === 'none' ? 'DEFLECT' : chunks[0]?.title;
  const score = method === 'none' ? topMatch?.score : chunks[0]?.similarity;
  const ok = c.expected === 'DEFLECT'
    ? got === 'DEFLECT'
    : c.expected.includes(got);

  console.log(`${ok ? 'PASS' : 'FAIL'}  ${(score ?? 0).toFixed(3)}  "${c.query}"`);
  console.log(`      -> ${got}${ok ? '' : `  (expected ${c.expected})`}`);
  ok ? pass++ : fail++;
}

console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail > 0 ? 1 : 0);
