// Zero-network unit test for netlify/functions/lib/retrieval.js and ask.js.
// Stubs fetch and the DB client; never calls Voyage, Anthropic or the DB.
// Run: node scripts/test_ask.mjs
import assert from 'node:assert/strict';
import {
  embedQuery, matchSections, retrieve, QUESTION_MATCH_THRESHOLD, TOP_K, VOYAGE_MODEL,
} from '../netlify/functions/lib/retrieval.js';
import { createHandler, cleanAnswer, deriveYear } from '../netlify/functions/ask.js';

// Hard stop on any real network use.
globalThis.fetch = () => { throw new Error('real fetch called in test'); };

let passed = 0;
async function test(name, fn) {
  try { await fn(); passed++; console.log(`ok   ${name}`); }
  catch (e) { console.log(`FAIL ${name}\n     ${e.stack}`); process.exitCode = 1; }
}

const EMB = [0.1, 0.2, 0.3];
const fetchOk = async (url, init) => {
  const body = JSON.parse(init.body);
  assert.equal(body.model, VOYAGE_MODEL);
  return { ok: true, status: 200, json: async () => ({ data: [{ embedding: EMB }] }) };
};
const quiet = (fn) => async (...a) => { const e = console.error; console.error = () => {}; try { return await fn(...a); } finally { console.error = e; } };

function stubSql(rows) {
  const calls = [];
  return { calls, query: async (text, params) => { calls.push({ text, params }); return { rows: rows.map(r => ({ ...r })) }; } };
}

const NOVO = {
  title: 'NOVO.R1',
  content: 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022), building Wegovycare.\n\nI led it end to end, a stealth transformation project[NOVO.R1.TRANSFORM], with learnings from LEO[LEO].',
  follow_ups: [{ text: 'how did you transform ways of working at Novo', target: 'NOVO.R1.TRANSFORM' }, { text: 'tell me about Skincoach', target: 'LEO.R2' }],
  similarity: 0.8234,
};
const LOW = { title: 'META.BOOKS', content: 'Books.', follow_ups: [], similarity: 0.41 };

console.log(`constants: threshold=${QUESTION_MATCH_THRESHOLD} top_k=${TOP_K} model=${VOYAGE_MODEL}`);

// --- retrieval.js ---
await test('embedQuery returns embedding from stubbed fetch', async () => {
  assert.deepEqual(await embedQuery('hi', { fetchImpl: fetchOk, env: { VOYAGE_API_KEY: 'x' } }), EMB);
});
await test('embedQuery retries on 429 then returns null on hard error', quiet(async () => {
  let n = 0;
  const f = async () => { n++; return n === 1 ? { ok: false, status: 429, text: async () => 'slow' } : { ok: false, status: 500, text: async () => 'boom' }; };
  assert.equal(await embedQuery('hi', { fetchImpl: f, env: {}, sleep: async () => {} }), null);
  assert.equal(n, 2);
}));
await test('matchSections sorts by similarity, applies topK, passes vector param', async () => {
  const sql = stubSql([LOW, NOVO]);
  const rows = await matchSections(EMB, { topK: 1, sql });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].title, 'NOVO.R1');
  assert.equal(sql.calls[0].params[0], '[0.1,0.2,0.3]');
  assert.match(sql.calls[0].text, /question_embedding <=> \$1::vector/);
});
await test('matchSections with threshold drops rows below it', async () => {
  assert.deepEqual(await matchSections(EMB, { topK: 1, threshold: 0.7, sql: stubSql([LOW]) }), []);
});
await test('matchSections returns [] on DB error', quiet(async () => {
  assert.deepEqual(await matchSections(EMB, { sql: { query: async () => { throw new Error('db down'); } } }), []);
}));
await test('retrieve returns top match above threshold', async () => {
  const { match, topMatch } = await retrieve('q', { fetchImpl: fetchOk, env: {}, sql: stubSql([LOW, NOVO]) });
  assert.equal(match.title, 'NOVO.R1');
  assert.equal(topMatch.title, 'NOVO.R1');
});
await test('retrieve returns null match below threshold (topMatch kept for logging)', async () => {
  const { match, topMatch } = await retrieve('q', { fetchImpl: fetchOk, env: {}, sql: stubSql([LOW]) });
  assert.equal(match, null);
  assert.equal(topMatch.title, 'META.BOOKS');
});
await test('retrieve reports embedding failure', quiet(async () => {
  const f = async () => ({ ok: false, status: 401, text: async () => 'no key' });
  const r = await retrieve('q', { fetchImpl: f, env: {}, sql: stubSql([NOVO]) });
  assert.equal(r.match, null);
  assert.equal(r.error, 'embedding failed');
}));

// --- ask.js ---
const req = (path, method = 'GET') => new Request(`http://localhost${path}`, { method });
const body = async (res) => JSON.parse(await res.text());
const headersOk = (res) => {
  assert.equal(res.headers.get('content-type'), 'application/json; charset=utf-8');
  assert.equal(res.headers.get('cache-control'), 'no-store');
};
const logs = [];
const origLog = console.log;
const withLogs = (fn) => async () => { console.log = (...a) => logs.push(a.join(' ')); try { await fn(); } finally { console.log = origLog; } };

await test('ask: match shape', withLogs(async () => {
  const h = createHandler({ retrieve: async () => ({ match: NOVO, topMatch: NOVO }) });
  const res = await h(req('/ask?q=what%20did%20you%20build%20at%20novo&asker=recruiter-agent'));
  assert.equal(res.status, 200); headersOk(res);
  const b = await body(res);
  assert.deepEqual(Object.keys(b), ['answer', 'section', 'source', 'strength', 'year', 'follow_ups', 'human_version', 'score']);
  assert.equal(b.section, 'NOVO.R1');
  assert.equal(b.source, 'TomBot NOVO.R1');
  assert.equal(b.strength, null);
  assert.equal(b.year, '2020-2022');
  assert.deepEqual(b.follow_ups, ['how did you transform ways of working at Novo', 'tell me about Skincoach']);
  assert.equal(b.human_version, '/projects/tombot/');
  assert.equal(b.score, 0.82);
  assert.ok(!b.answer.includes('[NOVO.R1.TRANSFORM]') && b.answer.includes('stealth transformation project, with learnings from LEO.'));
  assert.ok(logs.some(l => l.includes('"asker":"recruiter-agent"') && l.includes('"section":"NOVO.R1"') && l.includes('"query_length":' + 'what did you build at novo'.length)));
  origLog('     ' + JSON.stringify(b));
}));
await test('ask: no-match shape (200, no guess)', withLogs(async () => {
  const h = createHandler({ retrieve: async () => ({ match: null, topMatch: LOW }) });
  const res = await h(req('/ask?q=favourite%20colour'));
  assert.equal(res.status, 200); headersOk(res);
  const b = await body(res);
  assert.deepEqual(b, { answer: null, reason: 'no matching content', human_version: '/projects/tombot/' });
  origLog('     ' + JSON.stringify(b));
}));
await test('ask: missing q -> 400 with usage', async () => {
  let called = false;
  const h = createHandler({ retrieve: async () => { called = true; } });
  for (const p of ['/ask', '/ask?q=', '/ask?q=%20%20']) {
    const res = await h(req(p));
    assert.equal(res.status, 400); headersOk(res);
    const b = await body(res);
    assert.ok(b.error && b.usage.startsWith('Usage: GET /ask?q='));
  }
  assert.equal(called, false);
});
await test('ask: POST -> 405', async () => {
  const h = createHandler({ retrieve: async () => { throw new Error('should not run'); } });
  const res = await h(req('/ask?q=hi', 'POST'));
  assert.equal(res.status, 405); headersOk(res);
  assert.equal(res.headers.get('allow'), 'GET');
});
await test('ask: embedding failure -> 503, not a fake no-match', quiet(async () => {
  const h = createHandler({ retrieve: async () => ({ match: null, topMatch: null, error: 'embedding failed' }) });
  const res = await h(req('/ask?q=hi'));
  assert.equal(res.status, 503); headersOk(res);
}));
await test('ask: end to end on real retrieve with stubbed fetch + sql', async () => {
  const { retrieve: r } = await import('../netlify/functions/lib/retrieval.js');
  const h = createHandler({ retrieve: (q) => r(q, { fetchImpl: fetchOk, env: {}, sql: stubSql([NOVO, LOW]) }) });
  const b = await body(await h(req('/ask?q=novo')));
  assert.equal(b.section, 'NOVO.R1');
});

// --- helpers ---
await test('cleanAnswer strips questions/follow-ups/comments', async () => {
  const raw = '**Questions that route here:**\n- a\n- b\n\n<!-- note -->\nI did X.\n\n**Suggested follow-ups:**\n- "y" [META]';
  assert.equal(cleanAnswer(raw), 'I did X.');
});
await test('deriveYear: plain single year, none, ambiguous', async () => {
  assert.equal(deriveYear('Joined in 2016.'), '2016');
  assert.equal(deriveYear('No dates here.'), null);
  assert.equal(deriveYear('Things in 2014.\n\nAnd 2019.'), null);
  assert.equal(deriveYear('Lead (2016-present).'), '2016-present');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ', all green'}`);
