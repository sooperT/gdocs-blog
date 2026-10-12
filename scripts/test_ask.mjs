// Zero-network unit test for netlify/functions/lib/retrieval.js and ask.js.
// Stubs fetch and the DB client; never calls Voyage, Anthropic or the DB.
// Run: node scripts/test_ask.mjs
import assert from 'node:assert/strict';
import {
  embedQuery, matchSections, retrieve, QUESTION_MATCH_THRESHOLD, TOP_K, VOYAGE_MODEL,
  prepareQuery, prepareQuerySteps, normalizeQuery, expandContractions, expandAliases, expandSynonyms,
  listSections,
} from '../netlify/functions/lib/retrieval.js';
import { createHandler as createHandlerRaw, cleanAnswer, deriveYear, extractDirectAnswers, buildAttested, AGENT_TOP_K, HUMAN_VERSION, LINKEDIN_RECORD } from '../netlify/functions/ask.js';
import { RANKING_PATTERNS } from '../netlify/functions/lib/guard.js';
import { strengthFor } from '../netlify/functions/lib/strength.js';

// Never let a test reach a real database: drop any NILEDB_URL from the shell.
delete process.env.NILEDB_URL;

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

// Answers the aliases lookup with `aliases`, every other query with `rows`.
function stubSql(rows, aliases = []) {
  const calls = [];
  return { calls, query: async (text, params) => {
    calls.push({ text, params });
    const src = /FROM aliases/.test(text) ? aliases : rows;
    return { rows: src.map(r => ({ ...r })) };
  } };
}
const ALIASES = [{ alias: 'novo', canonical_name: 'Novo Nordisk' }];

const NOVO = {
  title: 'NOVO.R1',
  content: 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022), building Wegovycare.\n\nI led it end to end, a stealth transformation project[NOVO.R1.TRANSFORM], with learnings from LEO[LEO].',
  follow_ups: [{ text: 'how did you transform ways of working at Novo', target: 'NOVO.R1.TRANSFORM' }, { text: 'tell me about Skincoach', target: 'LEO.R2' }],
  // As the loader stores it (parse_content.py `attested`), JSONB parsed by pg.
  attested: [{ name: 'Erik Ejlskov Jensen', title: 'Principal Software Engineer', company: 'Context&', date: '2025-11-05',
    excerpt: 'I admired Toms ability to get the entire development team engaged in complex algorithms and turning them into simple solutions for the benefit of the end user.' }],
  direct_answers: [],
  similarity: 0.8234,
};
const mkRow = (title, similarity) => ({ title, content: `Section ${title} text.`, follow_ups: [], similarity });
const ATTESTED_KEYS = ['name', 'title', 'title_label', 'company', 'date', 'excerpt', 'record', 'tier'];
function assertAttested(list) {
  assert.ok(Array.isArray(list), 'attested must be an array');
  for (const a of list) {
    assert.deepEqual(Object.keys(a), ATTESTED_KEYS);
    assert.equal(a.tier, 'attested');
    assert.equal(a.title_label, 'current title');
    assert.equal(a.record, 'https://www.linkedin.com/in/tomstenson/details/recommendations/');
    assert.match(a.date, /^\d{4}-\d{2}-\d{2}$/);
    for (const k of ['name', 'title', 'company', 'excerpt']) assert.equal(typeof a[k], 'string');
    assert.doesNotMatch(a.name, /Martin Baker|Paul Hugh Mollin/);
  }
}
const LOW = { title: 'META.BOOKS', content: 'Books.', follow_ups: [], similarity: 0.41 };

// The stubbed map: every section the stubs can return, nothing else.
const MAP = [
  { id: 'LEO.R1', questions: ['what did you do at LEO', 'tell me about LEO Pharma', 'LEO turnaround', 'TREAT'] },
  { id: 'META.BOOKS', questions: ['what do you read'] },
  { id: 'NOVO.R1', questions: ['what did you build at Novo Nordisk', 'tell me about Wegovycare'] },
  { id: 'STYLE.DISCOVERY', questions: [] },
];
const stubListSections = async () => MAP.map(s => ({ ...s }));
// Every handler in this file: stubbed map, no rate limit, empty env.
const createHandler = (opts = {}) => createHandlerRaw({ listSections: stubListSections, limiter: null, env: {}, ...opts });

// Trust-contract invariants (PRD section 4, backlog item 22).
const RANK_WORDS = RANKING_PATTERNS;
function allStrings(v, out = []) {
  if (typeof v === 'string') out.push(v);
  else if (Array.isArray(v)) v.forEach(x => allStrings(x, out));
  else if (v && typeof v === 'object') Object.values(v).forEach(x => allStrings(x, out));
  return out;
}
function assertTrustContract(b) {
  for (const s of allStrings(b)) for (const p of RANK_WORDS) assert.doesNotMatch(s, p, 'ranking phrase in output');
  assert.match(b.human_version, /^https:\/\//, 'human_version must be absolute');
  if (b.answer === null) { assert.equal(typeof b.reason, 'string'); return; }
  for (const row of b.matches) {
    for (const k of ['section', 'source', 'year', 'score']) assert.ok(Object.hasOwn(row, k), `row missing ${k}`);
    assert.equal(typeof row.section, 'string');
    assert.equal(typeof row.source, 'string');
    assert.ok(row.year === null || typeof row.year === 'string');
    assert.equal(typeof row.score, 'number');
    assert.ok(MAP.some(s => s.id === row.section), 'section outside the map');
  }
}

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

// --- query preparation (moved from chat.js) ---
await test('prepareQuery: "tell me about tom" -> "tell me about yourself"', async () => {
  assert.equal(await prepareQuery('tell me about tom', { sql: stubSql([]) }), 'tell me about yourself');
});
await test('prepareQuery: "where has tom worked" -> "where have you worked"', async () => {
  assert.equal(await prepareQuery('where has tom worked', { sql: stubSql([]) }), 'where have you worked');
});
await test('prepareQuery: "what\'s tom\'s story" -> contractions + synonyms', async () => {
  const s = await prepareQuerySteps("what's tom's story", { sql: stubSql([]) });
  assert.equal(s.normalized, "what's your story");
  assert.equal(s.contractions, 'what is your story');
  assert.equal(s.final, 'what is your story journey arc background career');
});
await test('expandAliases: novo -> Novo Nordisk, no double expansion', async () => {
  assert.equal(await expandAliases('what did you build at novo', { sql: stubSql([], ALIASES) }), 'what did you build at Novo Nordisk');
  assert.equal(await expandAliases('what did you build at Novo Nordisk', { sql: stubSql([], ALIASES) }), 'what did you build at Novo Nordisk');
  assert.equal(await prepareQuery('what did Tom build at Novo', { sql: stubSql([], ALIASES) }), 'what did you build at Novo Nordisk');
});
await test('expandAliases: DB error leaves query unchanged', quiet(async () => {
  const sql = { query: async () => { throw new Error('db down'); } };
  assert.equal(await expandAliases('at novo', { sql }), 'at novo');
  assert.equal(await prepareQuery('where has tom worked', { sql }), 'where have you worked');
}));
await test('pure steps: contractions and synonyms only append/expand', async () => {
  assert.equal(normalizeQuery('was tom married'), 'were you married');
  assert.equal(expandContractions("who's they're"), 'who is they are');
  assert.equal(expandSynonyms('kids'), 'kids children family');
});
await test('retrieve embeds the prepared text, not the raw query', async () => {
  const sent = [];
  const f = async (url, init) => { sent.push(JSON.parse(init.body).input[0]); return fetchOk(url, init); };
  const sql = stubSql([NOVO], ALIASES);
  const { match } = await retrieve('what did Tom build at Novo', { fetchImpl: f, env: {}, sql });
  assert.deepEqual(sent, ['what did you build at Novo Nordisk']);
  assert.equal(match.title, 'NOVO.R1');
  assert.ok(/FROM aliases/.test(sql.calls[0].text) && /FROM chunks/.test(sql.calls[1].text));
});

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
  assert.deepEqual(Object.keys(b), ['answer', 'section', 'source', 'tier', 'strength', 'year', 'direct_answers', 'attested', 'follow_ups', 'score', 'matches', 'withheld', 'human_version']);
  assert.equal(b.direct_answers, null);
  assert.equal(b.withheld, 0);
  assert.equal(b.matches.length, 1);
  assert.deepEqual(Object.keys(b.matches[0]), ['section', 'answer', 'source', 'tier', 'year', 'strength', 'score', 'direct_answers', 'attested']);
  assert.equal(b.tier, 'self-reported');
  assert.equal(b.matches[0].tier, 'self-reported');
  assertAttested(b.attested);
  assert.equal(b.attested.length, 1);
  assert.deepEqual(b.attested, b.matches[0].attested);
  assert.equal(b.attested[0].name, 'Erik Ejlskov Jensen');
  assert.equal(b.attested[0].excerpt, NOVO.attested[0].excerpt);
  assert.ok(!b.answer.includes('admired'), 'attested excerpt must not leak into answer');
  assertTrustContract(b);
  assert.equal(b.section, 'NOVO.R1');
  assert.equal(b.source, 'TomBot NOVO.R1');
  assert.equal(b.strength, 'Led');
  assert.equal(b.matches[0].strength, 'Led');
  assert.equal(b.year, '2020-2022');
  assert.deepEqual(b.follow_ups, ['how did you transform ways of working at Novo', 'tell me about Skincoach']);
  assert.equal(b.human_version, 'https://takenbyninjas.com/projects/tombot/');
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
  assert.deepEqual(b, { answer: null, reason: 'no matching content', matches: [], human_version: HUMAN_VERSION });
  assertTrustContract(b);
  origLog('     ' + JSON.stringify(b));
}));
await test('ask: no q and no brief -> the map (every stubbed section, nothing else), no retrieval', async () => {
  let called = false;
  const h = createHandler({ retrieve: async () => { called = true; } });
  for (const p of ['/ask', '/ask?q=', '/ask?q=%20%20']) {
    const res = await h(req(p));
    assert.equal(res.status, 200); headersOk(res);
    const b = await body(res);
    assert.deepEqual(Object.keys(b), ['sections', 'count', 'human_version', 'usage']);
    assert.deepEqual(b.sections.map(s => s.id), MAP.map(s => s.id));
    assert.equal(b.count, MAP.length);
    assert.deepEqual(b.sections[0], { id: 'LEO.R1', routes: ['what did you do at LEO', 'tell me about LEO Pharma', 'LEO turnaround'] });
    assert.deepEqual(b.sections[3].routes, []);
    assert.equal(b.human_version, 'https://takenbyninjas.com/projects/tombot/');
    assert.ok(b.usage.startsWith('Usage: GET /ask'));
    if (p === '/ask') origLog('     ' + JSON.stringify(b).slice(0, 200) + '…');
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
  const h = createHandler({ retrieve: (q, o) => r(q, { ...o, fetchImpl: fetchOk, env: {}, sql: stubSql([NOVO, LOW]) }) });
  const b = await body(await h(req('/ask?q=novo')));
  assert.equal(b.section, 'NOVO.R1');
  assert.deepEqual(b.matches.map(m => m.section), ['NOVO.R1']);  // LOW is below 0.55
  assertTrustContract(b);
});

// --- agent retrieval profile (item 20) ---
const mk = (title, similarity, content = `Section ${title} text.`) => ({ title, content, follow_ups: [], similarity });
await test('profile: ask requests topK 5, chat constants unchanged (TOP_K 1, threshold 0.55)', async () => {
  assert.equal(AGENT_TOP_K, 5);
  assert.equal(TOP_K, 1);
  assert.equal(QUESTION_MATCH_THRESHOLD, 0.55);
  let opts;
  const h = createHandler({ retrieve: async (q, o) => { opts = o; return { match: NOVO, topMatch: NOVO, matches: [NOVO] }; } });
  await h(req('/ask?q=novo'));
  assert.equal(opts.topK, 5);
  assert.equal(opts.threshold, undefined);  // shared default, never overridden
});
await test('profile: up to 5 matches above 0.55, best first, scores per hit; best mirrored top-level', async () => {
  const rows = [mk('LEO.R1', 0.71), NOVO, mk('META.BOOKS', 0.60), mk('STYLE.DISCOVERY', 0.56), LOW, mk('LEO.R1', 0.54)];
  const { retrieve: r } = await import('../netlify/functions/lib/retrieval.js');
  const h = createHandler({ retrieve: (q, o) => r(q, { ...o, fetchImpl: fetchOk, env: {}, sql: stubSql(rows) }) });
  const b = await body(await h(req('/ask?q=what%20have%20you%20done')));
  assert.deepEqual(b.matches.map(m => [m.section, m.score]), [['NOVO.R1', 0.82], ['LEO.R1', 0.71], ['META.BOOKS', 0.6], ['STYLE.DISCOVERY', 0.56]]);
  assert.equal(b.section, 'NOVO.R1');
  assert.equal(b.answer, b.matches[0].answer);
  assert.equal(b.source, 'TomBot NOVO.R1');
  assertTrustContract(b);
});
await test('profile: never more than 5 matches even if retrieve returns more', async () => {
  const many = ['LEO.R1', 'META.BOOKS', 'NOVO.R1', 'STYLE.DISCOVERY', 'LEO.R1', 'NOVO.R1', 'META.BOOKS'].map((t, i) => mk(t, 0.9 - i * 0.01));
  const h = createHandler({ retrieve: async () => ({ match: many[0], topMatch: many[0], matches: many }) });
  const b = await body(await h(req('/ask?q=x')));
  assert.equal(b.matches.length, 5);
});
await test('retrieve returns matches (all above threshold, up to topK)', async () => {
  const rows = [mk('A', 0.9), mk('B', 0.7), mk('C', 0.56), mk('D', 0.5)];
  const res = await retrieve('q', { fetchImpl: fetchOk, env: {}, sql: stubSql(rows), topK: 5 });
  assert.deepEqual(res.matches.map(m => m.title), ['A', 'B', 'C']);
  assert.equal(res.match.title, 'A');
  const one = await retrieve('q', { fetchImpl: fetchOk, env: {}, sql: stubSql(rows) });
  assert.deepEqual(one.matches.map(m => m.title), ['A']);  // default topK 1, as chat
});
await test('direct_answers: block returned as lines and stripped from answer; null when absent', async () => {
  const content = 'Senior PM at Novo Nordisk (2020-2022).\n\n**Direct answers:**\n- Led: Wegovycare launch, 2021 [NOVO.R1]\n- Danish: not met\n\nMore prose here.';
  const { rest, lines } = extractDirectAnswers(content);
  assert.deepEqual(lines, ['Led: Wegovycare launch, 2021', 'Danish: not met']);
  assert.ok(!rest.includes('Direct answers'));
  assert.equal(extractDirectAnswers('No block.').lines, null);
  const h = createHandler({ retrieve: async () => ({ match: { ...NOVO, content }, matches: [{ ...NOVO, content }] }) });
  const b = await body(await h(req('/ask?q=novo')));
  assert.deepEqual(b.direct_answers, ['Led: Wegovycare launch, 2021', 'Danish: not met']);
  assert.deepEqual(b.matches[0].direct_answers, b.direct_answers);
  assert.equal(b.answer, 'Senior PM at Novo Nordisk (2020-2022).\n\nMore prose here.');
  assertTrustContract(b);
});
await test('direct_answers: column is read when filled, text parser is the fallback', async () => {
  const content = 'Senior PM (2020-2022).\n\n**Direct answers:**\n- From the text\n';
  const h = createHandler({ retrieve: async () => ({ matches: [{ ...NOVO, content, direct_answers: ['From the column [NOVO.R1]'] }] }) });
  assert.deepEqual((await body(await h(req('/ask?q=novo')))).direct_answers, ['From the column']);
  const h2 = createHandler({ retrieve: async () => ({ matches: [{ ...NOVO, content, direct_answers: [] }] }) });
  assert.deepEqual((await body(await h2(req('/ask?q=novo')))).direct_answers, ['From the text']);
  const h3 = createHandler({ retrieve: async () => ({ matches: [{ ...NOVO, content, direct_answers: '["As a JSON string"]' }] }) });
  assert.deepEqual((await body(await h3(req('/ask?q=novo')))).direct_answers, ['As a JSON string']);
});
await test('attested: [] when the column is null, missing, empty or malformed; tiers on every row', async () => {
  const rows = [
    { ...NOVO, title: 'NOVO.R1', attested: null },
    { ...mkRow('LEO.R1', 0.7), attested: undefined },
    { ...mkRow('STYLE.DISCOVERY', 0.65), attested: 'not json' },
    { ...mkRow('META.BOOKS', 0.6), attested: [{ name: 'No excerpt' }, 42] },
  ];
  const h = createHandler({ retrieve: async () => ({ matches: rows }) });
  const b = await body(await h(req('/ask?q=x')));
  assert.equal(b.matches.length, 4);
  for (const m of b.matches) { assert.deepEqual(m.attested, []); assert.equal(m.tier, 'self-reported'); }
  assert.deepEqual(b.attested, []);
  assertTrustContract(b);
});
await test('attested: JSON-string column parsed; deny-list runs on excerpts', async () => {
  const json = JSON.stringify([
    { name: 'A Person', title: 'Director, Innovation (Contract)', company: 'Acme & Co', date: '2026-03-16', excerpt: 'Plain praise.' },
    { name: 'B Person', title: 'CEO', company: 'B', date: '2016-04-12', excerpt: 'His salary was 900,000 DKK.' },
  ]);
  const { entries, withheld } = buildAttested(json);
  assertAttested(entries);
  assert.equal(entries[0].title, 'Director, Innovation (Contract)');
  assert.equal(entries[0].record, LINKEDIN_RECORD);
  assert.equal(entries[1].excerpt, '[withheld]');
  assert.equal(withheld, 1);
});
await test('matchSections selects attested and direct_answers; falls back on an old table (42703)', quiet(async () => {
  const sql = stubSql([{ ...NOVO }]);
  const rows = await matchSections(EMB, { sql });
  assert.match(sql.calls[0].text, /attested, direct_answers/);
  assert.deepEqual(rows[0].attested, NOVO.attested);
  const texts = [];
  const old = { query: async (text) => {
    texts.push(text);
    if (/attested/.test(text)) { const e = new Error('column "attested" does not exist'); e.code = '42703'; throw e; }
    return { rows: [{ title: 'NOVO.R1', content: 'x', similarity: 0.9 }] };
  } };
  const legacy = await matchSections(EMB, { sql: old });
  assert.equal(texts.length, 2);
  assert.doesNotMatch(texts[1], /attested/);
  assert.equal(legacy[0].attested, null);
  assert.equal(legacy[0].direct_answers, null);
  const other = { query: async () => { const e = new Error('boom'); e.code = '57P01'; throw e; } };
  assert.deepEqual(await matchSections(EMB, { sql: other }), []);
}));
await test('no Claude call anywhere in ?q= (no anthropic import in ask.js)', async () => {
  const { readFileSync } = await import('node:fs');
  const src = readFileSync(new URL('../netlify/functions/ask.js', import.meta.url), 'utf8');
  assert.doesNotMatch(src, /anthropic/i);
});
await test('listSections: one grouped query over chunks, question rows only', async () => {
  const sql = stubSql([{ title: 'NOVO.R1', questions: ['a', 'b', null] }, { title: 'META', questions: null }]);
  const out = await listSections({ sql });
  assert.deepEqual(out, [{ id: 'NOVO.R1', questions: ['a', 'b'] }, { id: 'META', questions: [] }]);
  assert.equal(sql.calls.length, 1);
  assert.match(sql.calls[0].text, /FROM chunks/);
  assert.match(sql.calls[0].text, /GROUP BY title/);
  assert.match(sql.calls[0].text, /question_text IS NOT NULL/);
});
await test('map is cached per instance (one listSections call for several requests)', async () => {
  let n = 0;
  const h = createHandler({ listSections: async () => { n++; return MAP; }, retrieve: async () => ({ match: NOVO, matches: [NOVO] }) });
  await h(req('/ask')); await h(req('/ask?q=a')); await h(req('/ask'));
  assert.equal(n, 1);
});

// --- isolation (item 17) ---
await test('db mismatch: retrieve without sql throws DbEnvError (no URL in message)', async () => {
  const env = { TOMBOT_ENV: 'staging', NILEDB_URL: 'postgres://u:secret@db.example:5432/niledb' };
  await assert.rejects(() => retrieve('q', { env, fetchImpl: fetchOk }), (e) => e.code === 'DB_ENV' && !e.message.includes('secret') && !e.message.includes('example'));
});
await test('db mismatch: ask turns it into 503 with the one-line reason, no stack, no URL', quiet(async () => {
  const env = { TOMBOT_ENV: 'staging', NILEDB_URL: 'postgres://u:secret@db.example:5432/niledb' };
  const { retrieve: r, listSections: ls } = await import('../netlify/functions/lib/retrieval.js');
  const h = createHandlerRaw({ env, limiter: null, retrieve: (q, o) => r(q, { ...o, fetchImpl: fetchOk }), listSections: () => ls({ env }) });
  for (const p of ['/ask?q=novo', '/ask']) {
    const res = await h(req(p));
    assert.equal(res.status, 503); headersOk(res);
    const text = await res.text();
    const b = JSON.parse(text);
    assert.match(b.error, /^database refused: staging must use a database whose name contains "staging"$/);
    assert.ok(!/secret|example|postgres:|\bat \w+ \(/.test(text));
  }
}));
await test('chat path unaffected: retrieve/prepare with an explicit pool never resolve the env', async () => {
  const env = { TOMBOT_ENV: 'staging', NILEDB_URL: 'postgres://u:p@h/niledb' };  // would be refused
  const { match } = await retrieve('novo', { env, fetchImpl: fetchOk, sql: stubSql([NOVO]) });
  assert.equal(match.title, 'NOVO.R1');
  assert.equal(await prepareQuery('tom', { sql: stubSql([]) }), 'you');
});
await test('AGENT_SIDE_ENABLED=false/0 -> 503 before anything runs', async () => {
  for (const v of ['false', '0', 'FALSE']) {
    let called = false;
    const h = createHandler({ env: { AGENT_SIDE_ENABLED: v }, retrieve: async () => { called = true; }, listSections: async () => { called = true; } });
    for (const p of ['/ask?q=hi', '/ask', '/ask?brief=x']) {
      const res = await h(req(p));
      assert.equal(res.status, 503);
      assert.deepEqual(await body(res), { error: 'agent side is switched off in this environment' });
    }
    assert.equal(called, false);
  }
  const on = createHandler({ env: { AGENT_SIDE_ENABLED: 'true' }, retrieve: async () => ({ match: NOVO, matches: [NOVO] }) });
  assert.equal((await on(req('/ask?q=x'))).status, 200);
});

// --- guard on /ask ---
await test('guard: deny-list on answers counts withheld; ranking text never leaves', async () => {
  const content = 'I led growth at Novo Nordisk (2020-2022).\nThe ideal candidate for any PM role.\nDay rate: 9.000 DKK.';
  const m = { ...NOVO, content };
  const h = createHandler({ retrieve: async () => ({ match: m, matches: [m] }) });
  const b = await body(await h(req('/ask?q=x')));
  assert.equal(b.answer, 'I led growth at Novo Nordisk (2020-2022).\n[withheld]\n[withheld]');
  assert.equal(b.withheld, 2);
  assertTrustContract(b);
});
await test('guard: section outside the map is dropped; only unknown -> null answer', async () => {
  const ghost = mk('GHOST.SECTION', 0.95);
  let h = createHandler({ retrieve: async () => ({ match: ghost, matches: [ghost, NOVO] }) });
  let b = await body(await h(req('/ask?q=x')));
  assert.deepEqual(b.matches.map(m => m.section), ['NOVO.R1']);
  assert.equal(b.section, 'NOVO.R1');
  h = createHandler({ retrieve: async () => ({ match: ghost, matches: [ghost] }) });
  b = await body(await h(req('/ask?q=x')));
  assert.equal(b.answer, null);
  assert.equal(b.reason, 'no matching content');
});
await test('guard: rate limit 20/min per IP on /ask -> 429 with Retry-After', async () => {
  const h = createHandlerRaw({ listSections: stubListSections, env: {}, retrieve: async () => ({ match: NOVO, matches: [NOVO] }) });
  const r = () => new Request('http://localhost/ask', { headers: { 'x-nf-client-connection-ip': '203.0.113.9' } });
  for (let i = 0; i < 20; i++) assert.equal((await h(r())).status, 200);
  const res = await h(r());
  assert.equal(res.status, 429);
  assert.ok(Number(res.headers.get('retry-after')) >= 1);
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

await test('strength: labelled section -> Led, unlabelled or missing -> null (item 25)', async () => {
  assert.equal(strengthFor('NOVO.R1'), 'Led');
  assert.equal(strengthFor('LEO.R1.TURNAROUND'), 'Led');
  assert.equal(strengthFor('LEO.R1'), null);
  assert.equal(strengthFor('META.BOOKS'), null);
  assert.equal(strengthFor(undefined), null);
  assert.equal(strengthFor('toString'), null);
});
await test('ask: stubbed match on an unlabelled section -> strength null', async () => {
  const STYLE = { title: 'STYLE.DISCOVERY', content: 'I run discovery with interviews and prototypes.', follow_ups: [], similarity: 0.7 };
  const h = createHandler({ retrieve: async () => ({ match: STYLE, topMatch: STYLE }) });
  const b = await body(await h(req('/ask?q=how%20do%20you%20run%20discovery')));
  assert.equal(b.section, 'STYLE.DISCOVERY');
  assert.equal(b.strength, null);
  assert.equal(b.matches[0].strength, null);
});
console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ', all green'}`);
