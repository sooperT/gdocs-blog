// Zero-network unit test for netlify/functions/agent-fetch.js.
// Stubs the file reader and the DB pool; never touches the DB or the network.
// Run: node scripts/test_agent_fetch.mjs
import assert from 'node:assert/strict';
import { createHandler, defaultReadFile, CACHE_CONTROL } from '../netlify/functions/agent-fetch.js';

globalThis.fetch = () => { throw new Error('real fetch called in test'); };

let passed = 0;
async function test(name, fn) {
  try { await fn(); passed++; console.log(`ok   ${name}`); }
  catch (e) { console.log(`FAIL ${name}\n     ${e.stack}`); process.exitCode = 1; }
}
const quiet = (fn) => async (...a) => {
  const w = console.warn, e = console.error; const seen = [];
  console.warn = (...m) => seen.push(m.join(' ')); console.error = (...m) => seen.push(m.join(' '));
  try { return await fn(seen, ...a); } finally { console.warn = w; console.error = e; }
};

const FILES = { 'for-agents/index.html': '<!DOCTYPE html><title>facts</title>', 'llms.txt': '# takenbyninjas.com\n' };
const readFile = (p) => { if (!(p in FILES)) throw new Error('no such file'); return FILES[p]; };
function stubPool() {
  const calls = [];
  return { calls, query: async (text, params) => { calls.push({ text, params }); return { rows: [] }; } };
}
const throwingPool = { query: async () => { throw new Error('relation "agent_fetches" does not exist'); } };

const BASE = 'https://takenbyninjas.com/.netlify/functions/agent-fetch';
const UA = 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot';
const req = (path, init = {}) => new Request(BASE + path, init);
// Netlify context stub with waitUntil, collecting the background promises.
function ctx(extra = {}) {
  const pending = [];
  return { pending, waitUntil: (p) => pending.push(p), ...extra };
}

await test('GET /for-agents/ -> 200 html, cache header, file body', async () => {
  const pool = stubPool(); const c = ctx();
  const res = await createHandler({ getPool: () => pool, readFile })(req('/page'), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/html; charset=utf-8');
  assert.equal(res.headers.get('cache-control'), CACHE_CONTROL);
  assert.equal(CACHE_CONTROL, 'public, max-age=86400');
  assert.equal(await res.text(), FILES['for-agents/index.html']);
  assert.equal(pool.calls.length, 1);
});

await test('GET /llms.txt -> 200 text/plain', async () => {
  const res = await createHandler({ getPool: () => stubPool(), readFile })(req('/llms'), ctx());
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/plain; charset=utf-8');
  assert.equal(await res.text(), FILES['llms.txt']);
});

await test('public paths also resolve (/for-agents/, /llms.txt)', async () => {
  const h = createHandler({ getPool: () => stubPool(), readFile });
  const a = await h(new Request('https://takenbyninjas.com/for-agents/'), ctx());
  const b = await h(new Request('https://takenbyninjas.com/llms.txt'), ctx());
  assert.equal(await a.text(), FILES['for-agents/index.html']);
  assert.equal(await b.text(), FILES['llms.txt']);
});

await test('throwing pool still returns 200 with the file (waitUntil path)', quiet(async (seen) => {
  const c = ctx();
  const res = await createHandler({ getPool: () => throwingPool, readFile })(req('/page'), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(await res.text(), FILES['for-agents/index.html']);
  assert.ok(seen.some(m => m.includes('log failed')), 'warned on failure');
}));

await test('throwing pool, no waitUntil, getPool itself throwing, null pool: all 200', quiet(async () => {
  for (const getPool of [() => throwingPool, () => { throw new Error('bad url'); }, () => null]) {
    const res = await createHandler({ getPool, readFile })(req('/llms'), {});
    assert.equal(res.status, 200);
    assert.equal(await res.text(), FILES['llms.txt']);
  }
}));

await test('POST -> 405 with Allow, nothing logged', async () => {
  const pool = stubPool();
  const res = await createHandler({ getPool: () => pool, readFile })(req('/page', { method: 'POST', body: 'x' }), ctx());
  assert.equal(res.status, 405);
  assert.equal(res.headers.get('allow'), 'GET, HEAD');
  assert.equal(pool.calls.length, 0);
});

await test('HEAD -> 200 headers, empty body, logged', async () => {
  const pool = stubPool(); const c = ctx();
  const res = await createHandler({ getPool: () => pool, readFile })(req('/llms', { method: 'HEAD' }), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/plain; charset=utf-8');
  assert.equal(res.headers.get('cache-control'), CACHE_CONTROL);
  assert.equal(await res.text(), '');
  assert.equal(pool.calls.length, 1);
});

await test('logged row: path, UA, referer, country, status; no IP, no query string', async () => {
  const pool = stubPool(); const c = ctx();
  const r = req('/page?utm_source=secret&q=who', { headers: {
    'user-agent': UA,
    'referer': 'https://chatgpt.com/c/abc?token=secret#frag',
    'x-country': 'DK',
    'x-nf-client-connection-ip': '203.0.113.7',
    'x-forwarded-for': '203.0.113.7',
  } });
  await createHandler({ getPool: () => pool, readFile })(r, c);
  await Promise.all(c.pending);
  const { text, params } = pool.calls[0];
  assert.match(text, /INSERT INTO agent_fetches \(path, user_agent, referer, country, status\)/);
  assert.deepEqual(params, ['/for-agents/', UA, 'https://chatgpt.com/c/abc', 'DK', 200]);
  const flat = JSON.stringify(pool.calls);
  assert.ok(!flat.includes('203.0.113.7'), 'no IP');
  assert.ok(!flat.includes('secret') && !flat.includes('utm_') && !flat.includes('?'), 'no query string');
});

await test('country falls back to context.geo, referer/UA absent -> null/empty', async () => {
  const pool = stubPool(); const c = ctx({ geo: { country: { code: 'SE' } } });
  await createHandler({ getPool: () => pool, readFile })(req('/llms'), c);
  await Promise.all(c.pending);
  assert.deepEqual(pool.calls[0].params, ['/llms.txt', '', null, 'SE', 200]);
});

await test('unknown subpath -> 404', async () => {
  const res = await createHandler({ getPool: () => stubPool(), readFile })(req('/other'), ctx());
  assert.equal(res.status, 404);
});

await test('default reader finds the real repo files (bundle layout fallback)', async () => {
  assert.match(defaultReadFile('for-agents/index.html'), /<!DOCTYPE html>/i);
  assert.match(defaultReadFile('llms.txt'), /^# takenbyninjas\.com/);
});

console.log(`\n${passed} passed${process.exitCode ? ', some FAILED' : ''}`);
