// Zero-network unit test for netlify/functions/agent-fetch.js.
// Stubs the file reader and the DB pool; never touches the DB or the network.
// Run: node scripts/test_agent_fetch.mjs
import assert from 'node:assert/strict';
import { robotsHeaders } from '../netlify/functions/agent-fetch.js';
import { createHandler, defaultReadFile, CACHE_CONTROL, RESOURCES } from '../netlify/functions/agent-fetch.js';

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

const FILES = {
  'for-agents/start.md': '# Start here\n\n## 0. What would your person like to do?\n\n## 1. Where things are\n',
  'for-agents/start/index.html': '<!DOCTYPE html><title>Start page</title><pre># Start here\n\n## 0. What would your person like to do?\n\n## 1. Where things are\n</pre>',
  'for-agents/sends.json': JSON.stringify({ sends: { 'novonesis-2026': { role: 'Senior Principal Innovation PM', company: 'Novonesis' } } }),
};
const readFile = (p) => { if (!(p in FILES)) throw new Error('no such file'); return FILES[p]; };
function stubPool() {
  const calls = [];
  return { calls, query: async (text, params) => { calls.push({ text, params }); return { rows: [] }; } };
}
const throwingPool = { query: async () => { throw new Error('relation "agent_fetches" does not exist'); } };

const BASE = 'https://takenbyninjas.com/.netlify/functions/agent-fetch';
const UA = 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot';
const req = (path, init = {}) => new Request(BASE + path, init);
// Netlify context stub with waitUntil, collecting the background promises.
function ctx(extra = {}) {
  const pending = [];
  return { pending, waitUntil: (p) => pending.push(p), ...extra };
}

await test('only the entry file is served (2026-10-19): RESOURCES is start + start-page', async () => {
  assert.deepEqual(Object.keys(RESOURCES).sort(), ['start', 'start-page']);
});

await test('GET /for-agents/start.md -> 200 text/plain, cache header, file body, logged', async () => {
  const pool = stubPool(); const c = ctx();
  const res = await createHandler({ getPool: () => pool, readFile })(req('/start'), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/plain; charset=utf-8');
  assert.equal(res.headers.get('cache-control'), CACHE_CONTROL);
  assert.equal(CACHE_CONTROL, 'public, max-age=300');
  assert.equal(await res.text(), FILES['for-agents/start.md']);
  assert.equal(pool.calls.length, 1);
  assert.equal(pool.calls[0].params[0], '/for-agents/start.md');
});

await test('GET /for-agents/start/ -> 200 html, logged as the page', async () => {
  const pool = stubPool(); const c = ctx({ deploy: { context: 'production' } });
  const res = await createHandler({ getPool: () => pool, readFile })(req('/start-page'), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/html; charset=utf-8');
  assert.equal(res.headers.get('x-robots-tag'), null);
  assert.equal(await res.text(), FILES['for-agents/start/index.html']);
  assert.equal(pool.calls[0].params[0], '/for-agents/start/');
});

await test('public paths also resolve (/for-agents/start.md, /for-agents/start, /for-agents/start/index.html)', async () => {
  const h = createHandler({ getPool: () => stubPool(), readFile });
  for (const [path, file] of [['/for-agents/start.md', 'for-agents/start.md'], ['/for-agents/start', 'for-agents/start/index.html'],
                              ['/for-agents/start/', 'for-agents/start/index.html'], ['/for-agents/start/index.html', 'for-agents/start/index.html']]) {
    const res = await h(new Request('https://takenbyninjas.com' + path), ctx());
    assert.equal(res.status, 200, path);
    assert.equal(await res.text(), FILES[file], path);
  }
});

await test('the facts page, llms.txt and the other agent pages are not served here (static files now)', async () => {
  const h = createHandler({ getPool: () => stubPool(), readFile });
  for (const path of ['/for-agents/', '/llms.txt', '/for-agents/stories/', '/for-agents/novo-nordisk/', '/for-agents/proof-points.json', '/for-agents/recommendations/']) {
    assert.equal((await h(new Request('https://takenbyninjas.com' + path), ctx())).status, 404, path);
  }
  assert.equal((await h(req('/page'), ctx())).status, 404);
  assert.equal((await h(req('/llms'), ctx())).status, 404);
});

await test('noindex outside production, none in production', async () => {
  assert.deepEqual(robotsHeaders({ deploy: { context: 'production' } }), {});
  assert.deepEqual(robotsHeaders({ deploy: { context: 'branch-deploy' } }), { 'X-Robots-Tag': 'noindex, nofollow' });
  const res = await createHandler({ getPool: () => stubPool(), readFile })(req('/start'), ctx({ deploy: { context: 'deploy-preview' } }));
  assert.equal(res.headers.get('x-robots-tag'), 'noindex, nofollow');
});

await test('outside production every absolute takenbyninjas.com link points at the deploy', async () => {
  const files = { ...FILES, 'for-agents/start.md': 'see https://takenbyninjas.com/for-agents/stories/\n## 1. Where things are\n' };
  const res = await createHandler({ getPool: () => stubPool(), readFile: (p) => files[p] })(
    new Request('https://staging--x.netlify.app/for-agents/start.md'), ctx({ deploy: { context: 'branch-deploy' } }));
  assert.ok((await res.text()).includes('https://staging--x.netlify.app/for-agents/stories/'));
});

await test('throwing pool still returns 200 with the file (waitUntil path)', quiet(async (seen) => {
  const c = ctx();
  const res = await createHandler({ getPool: () => throwingPool, readFile })(req('/start'), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(await res.text(), FILES['for-agents/start.md']);
  assert.ok(seen.some(m => m.includes('log failed')), 'warned on failure');
}));

await test('throwing pool, no waitUntil, getPool itself throwing, null pool: all 200', quiet(async () => {
  for (const getPool of [() => throwingPool, () => { throw new Error('bad url'); }, () => null]) {
    const res = await createHandler({ getPool, readFile })(req('/start'), {});
    assert.equal(res.status, 200);
    assert.equal(await res.text(), FILES['for-agents/start.md']);
  }
}));

await test('POST -> 405 with Allow, nothing logged', async () => {
  const pool = stubPool();
  const res = await createHandler({ getPool: () => pool, readFile })(req('/start', { method: 'POST', body: 'x' }), ctx());
  assert.equal(res.status, 405);
  assert.equal(res.headers.get('allow'), 'GET, HEAD');
  assert.equal(pool.calls.length, 0);
});

await test('HEAD -> 200 headers, empty body, logged', async () => {
  const pool = stubPool(); const c = ctx();
  const res = await createHandler({ getPool: () => pool, readFile })(req('/start', { method: 'HEAD' }), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/plain; charset=utf-8');
  assert.equal(await res.text(), '');
  assert.equal(pool.calls.length, 1);
});

await test('logged row: path, UA, referer without query, country, status; no IP, no query string', async () => {
  const pool = stubPool(); const c = ctx({ geo: { country: { code: 'DK' } } });
  const r = req('/start?utm_source=secret&q=who', { headers: {
    'user-agent': UA, referer: 'https://chatgpt.com/c/abc?x=1', 'x-nf-client-connection-ip': '203.0.113.9', 'x-country': 'DK' } });
  const res = await createHandler({ getPool: () => pool, readFile })(r, c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(pool.calls.length, 1);
  const { text, params } = pool.calls[0];
  assert.match(text, /insert into agent_fetches/i);
  assert.equal(params[0], '/for-agents/start.md');
  assert.equal(params[1], UA);
  assert.equal(params[2], 'https://chatgpt.com/c/abc');
  assert.equal(params[3], 'DK');
  assert.equal(params[4], 200);
  const flat = JSON.stringify(params);
  assert.ok(!flat.includes('203.0.113.9'), 'no IP');
  assert.ok(!flat.includes('secret') && !flat.includes('q=who'), 'no query string');
});

await test('unknown subpath -> 404, nothing logged', async () => {
  const pool = stubPool();
  const res = await createHandler({ getPool: () => pool, readFile })(req('/other'), ctx());
  assert.equal(res.status, 404);
  assert.equal(pool.calls.length, 0);
});

await test('every RESOURCES file is in netlify.toml included_files, with a forced rewrite; nothing else rewritten to the function', async () => {
  const { readFileSync } = await import('node:fs');
  const toml = readFileSync(new URL('../netlify.toml', import.meta.url), 'utf-8');
  const included = toml.match(/\[functions\."agent-fetch"\]\s*\n\s*included_files = \[([\s\S]*?)\]/)[1];
  for (const [key, r] of Object.entries(RESOURCES)) {
    assert.ok(included.includes(`"${r.file}"`), `${r.file} bundled`);
    const rule = new RegExp(`from = "${r.path.replace(/[.]/g, '\\.')}"\\s*\\n\\s*to = "/\\.netlify/functions/agent-fetch/${key}"\\s*\\n\\s*status = 200\\s*\\n\\s*force = true`);
    assert.match(toml, rule, `rewrite for ${r.path}`);
  }
  assert.ok(included.includes('"for-agents/sends.json"'), 'sends.json bundled for the tagged entry file');
  const targets = [...toml.matchAll(/to = "\/\.netlify\/functions\/agent-fetch\/([^"]+)"/g)].map(m => m[1]).sort();
  assert.deepEqual(targets, ['start', 'start-page', 'start/:splat']);
  assert.match(toml, /from = "\/for-agents\/README\.md"\s*\n\s*to = "\/for-agents\/start\.md"\s*\n\s*status = 301/);
  assert.ok(toml.indexOf('"/for-agents/README.md"') < toml.indexOf('from = "/for-agents/start.md"'), '301 before the start.md rewrite');
  assert.match(toml, /for = "\/for-agents\/start\.md"[\s\S]*?Content-Type = "text\/plain; charset=utf-8"/);
});

await test('default reader finds the real repo files (bundle layout fallback)', async () => {
  for (const r of Object.values(RESOURCES)) assert.ok(defaultReadFile(r.file).length > 0, r.file);
  assert.match(defaultReadFile('for-agents/start.md'), /^# Tom Stenson/);
});

await test('tagged start: /for-agents/start/<tag>.md serves start.md with the tag line, logs the tagged path and meta.tag; bad tags 404', async () => {
  const pool = stubPool(); const c = ctx({ deploy: { context: 'production' } });
  const h = createHandler({ getPool: () => pool, readFile });
  const res = await h(new Request('https://takenbyninjas.com/for-agents/start/novonesis-2026.md'), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/plain; charset=utf-8');
  const text = await res.text();
  assert.ok(text.includes('# Start here'), 'serves start.md');
  assert.ok(text.includes("Tom's application for Senior Principal Innovation PM at Novonesis"), 'send context from sends.json');
  assert.ok(!text.includes('/for-agents/fit/'), 'no per-send fit link (2026-10-19)');
  assert.ok(text.indexOf('## 0b. About this copy') < text.indexOf('## 1. Where things are'), 'inserted before section 1');
  const unknown = await (await h(new Request('https://takenbyninjas.com/for-agents/start/other-tag.md'), c)).text();
  assert.ok(unknown.includes('came with a specific CV send') && !unknown.includes('application for'), 'unknown tag: generic note');
  assert.equal(pool.calls[0].params[0], '/for-agents/start/novonesis-2026.md');
  assert.equal(pool.calls[0].params[5] && JSON.parse(pool.calls[0].params[5]).tag, 'novonesis-2026');
  const page = await h(new Request('https://takenbyninjas.com/for-agents/start/novonesis-2026/'), c);
  assert.equal(page.headers.get('content-type'), 'text/html; charset=utf-8');
  assert.ok((await page.text()).includes('About this copy'), 'HTML page gets the line too');
  for (const bad of ['/for-agents/start/Bad_Tag.md', '/for-agents/start/' + 'a'.repeat(41) + '.md', '/for-agents/start/x/y.md']) {
    assert.equal((await h(new Request('https://takenbyninjas.com' + bad), c)).status, 404, bad);
  }
});

console.log(`\n${passed} passed${process.exitCode ? ', some FAILED' : ''}`);
