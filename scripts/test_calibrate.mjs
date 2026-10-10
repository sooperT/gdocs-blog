// Zero-network unit test for netlify/functions/calibrate.js (W4 brief calibration).
// Stubs fetch (Voyage), the sql pool and the Anthropic call. Never calls an API.
// Run: node scripts/test_calibrate.mjs
import assert from 'node:assert/strict';
import {
  splitBriefHeuristic, splitBriefLLM, parseRequirementArray, buildRow, createCalibrateHandler,
  SPLITTER_SYSTEM_PROMPT, SPLITTER_MODEL, MAX_BRIEF_CHARS,
} from '../netlify/functions/calibrate.js';
import { createHandler as createAskHandler } from '../netlify/functions/ask.js';
import { retrieve as realRetrieve } from '../netlify/functions/lib/retrieval.js';

// Hard stop on any real network use.
globalThis.fetch = () => { throw new Error('real fetch called in test'); };

const logs = [];
const origLog = console.log;
let passed = 0;
async function test(name, fn) {
  try { await fn(); passed++; console.log(`ok   ${name}`); }
  catch (e) { console.log(`FAIL ${name}\n     ${e.stack}`); process.exitCode = 1; }
}
const quiet = (fn) => async (...a) => { const e = console.error; console.error = () => {}; try { return await fn(...a); } finally { console.error = e; } };

const JD = `Senior Product Manager, Health Platform (Copenhagen, hybrid)
We are a fast-growing digital health company building tools for patients and clinicians.
What you'll bring:
- 5+ years of product management experience in B2C or B2B SaaS
- Track record of launching mobile apps from zero to one
- Comfortable working with regulated data (GDPR, medical device rules)
- Experience leading cross-functional squads of engineers and designers
- Hands-on with discovery: interviews, prototypes, experiments
1. Strong stakeholder management with senior leadership
You must have 5 years of experience in a product role. Danish is a plus but you should be fluent in English.
We offer a great pension, lunch and a dog-friendly office.`;

const NOVO = {
  title: 'NOVO.R1',
  content: 'Senior Product Manager at Novo Nordisk (Mar 2020 - Feb 2022), building Wegovycare.\n\nI launched it in 5 markets, a stealth transformation project[NOVO.R1.TRANSFORM]. ' + 'More detail about the work. '.repeat(30),
  follow_ups: [],
  similarity: 0.8234,
};
const NOYEAR = { title: 'STYLE.DISCOVERY', content: 'I run discovery with interviews and prototypes.', follow_ups: [], similarity: 0.66 };
const LOW = { title: 'META.BOOKS', content: 'Books.', follow_ups: [], similarity: 0.41 };

const EMB = [0.1, 0.2, 0.3];
const fetchOk = async () => ({ ok: true, status: 200, json: async () => ({ data: [{ embedding: EMB }] }) });
const stubSql = (rows) => ({ query: async () => ({ rows: rows.map(r => ({ ...r })) }) });
// Real retrieve, stubbed Voyage + DB: Danish requirement gets only a weak row.
const stubRetrieve = (q) => realRetrieve(q, {
  fetchImpl: fetchOk, env: {}, sql: stubSql(/danish/i.test(q) ? [LOW] : /discovery/i.test(q) ? [NOYEAR] : [NOVO, LOW]),
});
const noAnthropic = async () => { throw new Error('Anthropic must not be called'); };

const req = (path, init = {}) => new Request(`http://localhost${path}`, init);
const body = async (res) => JSON.parse(await res.text());
const headersOk = (res) => {
  assert.equal(res.headers.get('content-type'), 'application/json; charset=utf-8');
  assert.equal(res.headers.get('cache-control'), 'no-store');
};

console.log(`splitter model=${SPLITTER_MODEL} max_brief=${MAX_BRIEF_CHARS}`);

// --- splitters ---
await test('heuristic: sample JD -> 5..12 requirements, no duplicates, verbatim', async () => {
  const reqs = splitBriefHeuristic(JD);
  origLog('     ' + JSON.stringify(reqs));
  assert.ok(reqs.length >= 5 && reqs.length <= 12, `got ${reqs.length}`);
  assert.equal(new Set(reqs.map(r => r.toLowerCase())).size, reqs.length);
  assert.ok(reqs.includes('5+ years of product management experience in B2C or B2B SaaS'));
  assert.ok(reqs.includes('You must have 5 years of experience in a product role.'));
  assert.ok(reqs.includes('Strong stakeholder management with senior leadership'));
  assert.ok(!reqs.some(r => /pension|dog-friendly/.test(r)));
  for (const r of reqs) assert.ok(JD.includes(r), `not verbatim: ${r}`);
});
await test('heuristic: dedupes repeats and caps at 12', async () => {
  const many = Array.from({ length: 20 }, (_, i) => `- Requirement number ${i}`).join('\n') + '\n- Requirement number 0';
  const reqs = splitBriefHeuristic(many);
  assert.equal(reqs.length, 12);
  assert.equal(splitBriefHeuristic('- Same thing\n* same thing.\n- SAME THING').length, 1);
});
await test('llm: parses stubbed JSON array, sends the fixed prompt', async () => {
  let params;
  const createMessage = async (p) => { params = p; return { content: [{ type: 'text', text: '["5+ years of product management experience", "Danish is a plus"]' }] }; };
  const r = await splitBriefLLM(JD, { createMessage });
  assert.deepEqual(r, { requirements: ['5+ years of product management experience', 'Danish is a plus'], splitter: 'llm' });
  assert.equal(params.model, 'claude-sonnet-5');
  assert.equal(params.system, SPLITTER_SYSTEM_PROMPT);
  assert.ok(params.max_tokens <= 1024);
  assert.equal(params.temperature, undefined);
  assert.equal(params.messages[0].content, JD);
});
await test('llm: fenced array parses; malformed reply falls back to heuristic', quiet(async () => {
  assert.deepEqual(parseRequirementArray('```json\n["a requirement"]\n```'), ['a requirement']);
  for (const text of ['Here are the requirements: 1. foo', '[1, 2]', '[]', '{"a": 1}']) {
    const r = await splitBriefLLM(JD, { createMessage: async () => ({ content: [{ type: 'text', text }] }) });
    assert.equal(r.splitter, 'heuristic');
    assert.deepEqual(r.requirements, splitBriefHeuristic(JD));
  }
  const thrown = await splitBriefLLM(JD, { createMessage: async () => { throw Object.assign(new Error('x'), { status: 529 }); } });
  assert.equal(thrown.splitter, 'heuristic');
}));
await test('system prompt: no facts about Tom, no ranking language', async () => {
  assert.doesNotMatch(SPLITTER_SYSTEM_PROMPT, /\b(?:tom|stenson|novo|leo|candidates?|rank\w*|scores?|fit|strong\w*|best|ideal)\b/i);
});

// --- rows ---
await test('row above threshold with year + outcome: met, evidence trimmed to 400', async () => {
  const row = buildRow('5+ years of product management experience', NOVO);
  assert.deepEqual(Object.keys(row), ['requirement', 'met', 'evidence', 'strength', 'year', 'source', 'score']);
  assert.equal(row.met, 'met');
  assert.equal(row.evidence.length, 403);
  assert.ok(row.evidence.endsWith('...'));
  assert.ok(!row.evidence.includes('[NOVO.R1.TRANSFORM]'));
  assert.equal(row.year, '2020-2022');
  assert.equal(row.source, 'TomBot NOVO.R1');
  assert.equal(row.strength, null);
  assert.equal(row.score, 0.82);
});
await test('row above threshold with no year: partial, short evidence not cut', async () => {
  const row = buildRow('Hands-on with discovery', NOYEAR);
  assert.equal(row.met, 'partial');
  assert.equal(row.evidence, 'I run discovery with interviews and prototypes.');
  assert.equal(row.year, null);
});
await test('row below threshold: not met, null evidence and source', async () => {
  assert.deepEqual(buildRow('Danish is a plus', null),
    { requirement: 'Danish is a plus', met: 'not met', evidence: null, strength: null, year: null, source: null, score: null });
});

// --- handler ---
const withLogs = (fn) => async () => { logs.length = 0; console.log = (...a) => logs.push(a.join(' ')); try { await fn(); } finally { console.log = origLog; } };
const handler = createCalibrateHandler({ retrieve: stubRetrieve, createMessage: noAnthropic, env: {} });
const JD2 = '- Fluent in Danish\n- Shipped consumer health apps\n- Hands-on with discovery';

await test('POST JSON body: response shape, heuristic splitter without a key', withLogs(async () => {
  const res = await handler(req('/ask/brief', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ brief: JD2, asker: 'recruiter-agent' }) }));
  assert.equal(res.status, 200); headersOk(res);
  const b = await body(res);
  assert.deepEqual(Object.keys(b), ['brief', 'rows', 'human_version', 'note']);
  assert.deepEqual(b.brief, { requirements: 3, splitter: 'heuristic' });
  assert.deepEqual(b.rows.map(r => [r.requirement, r.met]), [['Fluent in Danish', 'not met'], ['Shipped consumer health apps', 'met'], ['Hands-on with discovery', 'partial']]);
  assert.equal(b.human_version, '/projects/tombot/');
  assert.equal(b.note, "Evidence only. 'not met' means TomBot content has nothing on it, not that Tom lacks it.");
  origLog('     ' + JSON.stringify({ ...b, rows: b.rows.map(r => ({ ...r, evidence: r.evidence && r.evidence.slice(0, 40) + '…' })) }));
}));
await test('POST text/plain body works', async () => {
  const res = await handler(req('/ask/brief', { method: 'POST', headers: { 'content-type': 'text/plain' }, body: JD2 }));
  assert.equal(res.status, 200);
  assert.equal((await body(res)).brief.requirements, 3);
});
await test('LLM splitter used when ANTHROPIC_API_KEY is set', async () => {
  const h = createCalibrateHandler({ retrieve: stubRetrieve, env: { ANTHROPIC_API_KEY: 'stub' },
    createMessage: async () => ({ content: [{ type: 'text', text: '["Fluent in Danish"]' }] }) });
  const b = await body(await h(req('/ask/brief?brief=' + encodeURIComponent(JD2))));
  assert.deepEqual(b.brief, { requirements: 1, splitter: 'llm' });
});
await test('GET /ask?brief= via ask.js; q and brief together -> brief wins, note says so', async () => {
  const ask = createAskHandler({ retrieve: stubRetrieve, calibrate: handler });
  const b = await body(await ask(req('/ask?q=hello&brief=' + encodeURIComponent(JD2))));
  assert.equal(b.brief.requirements, 3);
  assert.match(b.note, /brief was used and q was ignored/);
});
await test('brief over 8000 chars -> 413; empty -> 400; bad JSON -> 400; PUT -> 405', async () => {
  const big = 'x'.repeat(MAX_BRIEF_CHARS + 1);
  let res = await handler(req('/ask/brief', { method: 'POST', headers: { 'content-type': 'text/plain' }, body: big }));
  assert.equal(res.status, 413); headersOk(res); assert.ok((await body(res)).error);
  res = await handler(req('/ask/brief', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ brief: big }) }));
  assert.equal(res.status, 413);
  for (const r of [req('/ask/brief?brief=%20'), req('/ask/brief', { method: 'POST', body: '' }),
    req('/ask/brief', { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' })]) {
    res = await handler(r); assert.equal(res.status, 400); headersOk(res);
  }
  res = await handler(req('/ask/brief', { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{nope' }));
  assert.equal(res.status, 400);
  res = await handler(req('/ask/brief', { method: 'PUT', body: 'x' }));
  assert.equal(res.status, 405);
});
await test('retrieval failure -> 503', quiet(async () => {
  const h = createCalibrateHandler({ retrieve: async () => ({ match: null, topMatch: null, error: 'embedding failed' }), env: {} });
  assert.equal((await h(req('/ask/brief?brief=' + encodeURIComponent(JD2)))).status, 503);
}));
await test('log line: one line, counts only, no brief text', withLogs(async () => {
  const res = await handler(req('/ask/brief', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ brief: JD, asker: 'hiring-manager' }) }));
  assert.equal(res.status, 200);
  assert.equal(logs.length, 1);
  const line = logs[0];
  origLog('     ' + line);
  const parsed = JSON.parse(line.replace(/^\[ask:brief\] /, ''));
  assert.deepEqual(Object.keys(parsed), ['asker', 'requirements', 'met', 'partial', 'not_met', 'splitter']);
  assert.equal(parsed.asker, 'hiring-manager');
  for (const r of splitBriefHeuristic(JD)) assert.ok(!line.includes(r));
  for (const word of ['Copenhagen', 'GDPR', 'Danish', 'stakeholder', 'product']) assert.ok(!line.includes(word), word);
}));

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ', all green'}`);
