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
  'for-agents/index.html': '<!DOCTYPE html><title>facts</title>',
  'llms.txt': '# takenbyninjas.com\n',
  'for-agents/start.md': '# Start here\n',
  'for-agents/wegovycare/index.html': '<!DOCTYPE html><title>Wegovycare</title>',
  'for-agents/treat-turnaround/index.html': '<!DOCTYPE html><title>TREAT</title>',
  'for-agents/recommendations/index.html': '<!DOCTYPE html><title>Recommendations</title>',
  'for-agents/opbeat/index.html': '<!DOCTYPE html><title>Opbeat</title>',
  'for-agents/pages.json': JSON.stringify({ pages: {
    opbeat: { path: '/for-agents/opbeat/', file: 'for-agents/opbeat/index.html', title: 'Opbeat' },
    '../evil': { path: '/x', file: '../.env', title: 'bad slug' },
    wegovycare: { path: '/for-agents/wegovycare/', file: 'for-agents/wegovycare/index.html', title: 'dupe of RESOURCES' },
  } }),
};
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
  assert.match(text, /INSERT INTO agent_fetches \(path, user_agent, referer, country, status, meta\)/);
  assert.deepEqual(params, ['/for-agents/', UA, 'https://chatgpt.com/c/abc', 'DK', 200, null]);
  const flat = JSON.stringify(pool.calls);
  assert.ok(!flat.includes('203.0.113.7'), 'no IP');
  assert.ok(!flat.includes('secret') && !flat.includes('utm_') && !flat.includes('?'), 'no query string');
});

await test('country falls back to context.geo, referer/UA absent -> null/empty', async () => {
  const pool = stubPool(); const c = ctx({ geo: { country: { code: 'SE' } } });
  await createHandler({ getPool: () => pool, readFile })(req('/llms'), c);
  await Promise.all(c.pending);
  assert.deepEqual(pool.calls[0].params, ['/llms.txt', '', null, 'SE', 200, null]);
});

await test('unknown subpath -> 404', async () => {
  const res = await createHandler({ getPool: () => stubPool(), readFile })(req('/other'), ctx());
  assert.equal(res.status, 404);
});

// Item 26: start.md and the two case studies are counted like the facts page.
const NEW = [
  { key: 'start', pub: '/for-agents/start.md', logged: '/for-agents/start.md', file: 'for-agents/start.md', type: 'text/markdown; charset=utf-8' },
  { key: 'wegovycare', pub: '/for-agents/wegovycare/', logged: '/for-agents/wegovycare/', file: 'for-agents/wegovycare/index.html', type: 'text/html; charset=utf-8' },
  { key: 'treat-turnaround', pub: '/for-agents/treat-turnaround/', logged: '/for-agents/treat-turnaround/', file: 'for-agents/treat-turnaround/index.html', type: 'text/html; charset=utf-8' },
  { key: 'recommendations', pub: '/for-agents/recommendations/', logged: '/for-agents/recommendations/', file: 'for-agents/recommendations/index.html', type: 'text/html; charset=utf-8' },
];
for (const r of NEW) {
  await test(`GET ${r.pub} -> 200 ${r.type.split(';')[0]}, cache header, logged as ${r.logged}`, async () => {
    const pool = stubPool(); const c = ctx({ deploy: { context: 'production' } });
    const res = await createHandler({ getPool: () => pool, readFile })(req('/' + r.key), c);
    await Promise.all(c.pending);
    assert.equal(res.status, 200);
    assert.equal(res.headers.get('content-type'), r.type);
    assert.equal(res.headers.get('cache-control'), CACHE_CONTROL);
    assert.equal(res.headers.get('x-robots-tag'), null);
    assert.equal(await res.text(), FILES[r.file]);
    assert.equal(pool.calls.length, 1);
    assert.equal(pool.calls[0].params[0], r.logged);
  });
  await test(`${r.pub}: public path resolves, noindex outside production, throwing pool still 200`, quiet(async () => {
    const c = ctx({ deploy: { context: 'branch-deploy' } });
    for (const path of [r.pub, r.pub.replace(/\/$/, '')]) {
      const res = await createHandler({ getPool: () => throwingPool, readFile })(new Request('https://takenbyninjas.com' + path), c);
      await Promise.all(c.pending);
      assert.equal(res.status, 200);
      assert.equal(res.headers.get('x-robots-tag'), 'noindex, nofollow');
      assert.equal(await res.text(), FILES[r.file]);
    }
  }));
}

await test('case-study paths do not fall through to the facts page', async () => {
  assert.equal(RESOURCES.page.file, 'for-agents/index.html');
  const h = createHandler({ getPool: () => stubPool(), readFile });
  const res = await h(new Request('https://takenbyninjas.com/for-agents/wegovycare/index.html'), ctx());
  assert.equal(await res.text(), FILES['for-agents/wegovycare/index.html']);
  const other = await h(new Request('https://takenbyninjas.com/for-agents/unknown/'), ctx());
  assert.equal(other.status, 404);
});

await test('every RESOURCES file is in netlify.toml included_files, with a forced rewrite', async () => {
  const { readFileSync } = await import('node:fs');
  const toml = readFileSync(new URL('../netlify.toml', import.meta.url), 'utf-8');
  const included = toml.match(/included_files = \[([\s\S]*?)\]/)[1];
  for (const [key, r] of Object.entries(RESOURCES)) {
    assert.ok(included.includes(`"${r.file}"`), `${r.file} bundled`);
    const rule = new RegExp(`from = "${r.path.replace(/[.]/g, '\\.')}"\\s*\\n\\s*to = "/\\.netlify/functions/agent-fetch/${key}"\\s*\\n\\s*status = 200\\s*\\n\\s*force = true`);
    assert.match(toml, rule, `rewrite for ${r.path}`);
  }
  assert.match(toml, /from = "\/for-agents\/README\.md"\s*\n\s*to = "\/for-agents\/start\.md"\s*\n\s*status = 301/);
  assert.ok(toml.indexOf('"/for-agents/README.md"') < toml.indexOf('from = "/for-agents/start.md"'), '301 before the start.md rewrite');
  assert.match(toml, /for = "\/for-agents\/start\.md"[\s\S]*?Content-Type = "text\/markdown; charset=utf-8"/);
});

await test('default reader finds the real repo files (bundle layout fallback)', async () => {
  assert.match(defaultReadFile('for-agents/index.html'), /<!DOCTYPE html>/i);
  assert.match(defaultReadFile('llms.txt'), /^# takenbyninjas\.com/);
  for (const r of NEW) assert.ok(defaultReadFile(r.file).length > 0, r.file);
});

await test('manifest page (pages.json): /for-agents/opbeat/ -> 200 html, logged; bad slug ignored; RESOURCES win', async () => {
  const pool = stubPool(); const c = ctx({ deploy: { context: 'production' } });
  const h = createHandler({ getPool: () => pool, readFile });
  for (const path of ['/for-agents/opbeat/', '/for-agents/opbeat', '/.netlify/functions/agent-fetch/opbeat']) {
    const res = await h(new Request('https://takenbyninjas.com' + path), c);
    await Promise.all(c.pending);
    assert.equal(res.status, 200, path);
    assert.equal(res.headers.get('content-type'), 'text/html; charset=utf-8');
    assert.equal(await res.text(), FILES['for-agents/opbeat/index.html']);
  }
  assert.equal(pool.calls.length, 3);
  assert.equal(pool.calls[0].params[0], '/for-agents/opbeat/');
  assert.equal((await h(new Request('https://takenbyninjas.com/x'), c)).status, 404);
  assert.equal(await (await h(new Request('https://takenbyninjas.com/for-agents/wegovycare/'), c)).text(), FILES['for-agents/wegovycare/index.html']);
});
await test('manifest missing or malformed: RESOURCES still resolve, unknown slug 404', quiet(async () => {
  const noManifest = (p) => { if (p === 'for-agents/pages.json') throw new Error('no such file'); return readFile(p); };
  const h = createHandler({ getPool: () => stubPool(), readFile: noManifest });
  const c = ctx({ deploy: { context: 'production' } });
  assert.equal((await h(new Request('https://takenbyninjas.com/llms.txt'), c)).status, 200);
  assert.equal((await h(new Request('https://takenbyninjas.com/for-agents/opbeat/'), c)).status, 404);
}));
await test('tagged start: /for-agents/start/<tag>.md serves start.md with the tag line, logs the tagged path and meta.tag; bad tags 404', async () => {
  const pool = stubPool(); const c = ctx({ deploy: { context: 'production' } });
  const h = createHandler({ getPool: () => pool, readFile });
  const res = await h(new Request('https://takenbyninjas.com/for-agents/start/novonesis-2026.md'), c);
  await Promise.all(c.pending);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'text/markdown; charset=utf-8');
  const text = await res.text();
  assert.ok(text.startsWith(FILES['for-agents/start.md'].trim()) || text.includes('# Start here'), 'serves start.md');
  assert.equal(pool.calls[0].params[0], '/for-agents/start/novonesis-2026.md');
  assert.deepEqual(JSON.parse(pool.calls[0].params[5]), { tag: 'novonesis-2026' });
  const rewritten = await h(req('/start/novonesis-2026.md'), c);
  assert.equal(rewritten.status, 200);
  for (const bad of ['/for-agents/start/Bad_Tag.md', '/for-agents/start/' + 'x'.repeat(41) + '.md', '/for-agents/start/x.txt']) {
    assert.equal((await h(new Request('https://takenbyninjas.com' + bad), c)).status, 404, bad);
  }
});
console.log(`\n${passed} passed${process.exitCode ? ', some FAILED' : ''}`);

// Non-production deploys mark function responses noindex; production does not.
{
  const assert = (await import('node:assert/strict')).default;
  assert.deepEqual(robotsHeaders({ deploy: { context: 'branch-deploy' } }), { 'X-Robots-Tag': 'noindex, nofollow' });
  assert.deepEqual(robotsHeaders({ deploy: { context: 'deploy-preview' } }), { 'X-Robots-Tag': 'noindex, nofollow' });
  assert.deepEqual(robotsHeaders({ deploy: { context: 'production' } }), {});
  assert.deepEqual(robotsHeaders(undefined), {});
  console.log('ok   robotsHeaders: noindex outside production');
}
