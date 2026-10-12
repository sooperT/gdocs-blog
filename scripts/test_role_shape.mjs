// Zero-network tests for netlify/functions/lib/role_shape.js (backlog item 27).
// Run: node scripts/test_role_shape.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { classifyBrief, SENIORITY, FUNCTION, SECTOR } from '../netlify/functions/lib/role_shape.js';

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log(`ok   ${name}`); }
  catch (e) { console.log(`FAIL ${name}\n     ${e.stack}`); process.exitCode = 1; }
}

test('every label comes from its fixed list', () => {
  for (const text of ['', 'Senior Product Manager, fintech', 'xyzzy plugh', 'Head of Engineering at a hospital']) {
    const s = classifyBrief(text);
    assert.ok(SENIORITY.includes(s.seniority));
    assert.ok(FUNCTION.includes(s.function));
    assert.ok(SECTOR.includes(s.sector));
  }
});
test('empty or unrecognised brief is unknown on all three', () => {
  assert.deepEqual(classifyBrief(''), { seniority: 'unknown', function: 'unknown', sector: 'unknown' });
  assert.deepEqual(classifyBrief(null), { seniority: 'unknown', function: 'unknown', sector: 'unknown' });
});
test('specific word beats the generic one', () => {
  assert.equal(classifyBrief('Senior Product Lead').seniority, 'lead');
  assert.equal(classifyBrief('Head of Product, senior role').seniority, 'head');
  assert.equal(classifyBrief('pharma product manager in healthcare').sector, 'pharma');
});
test('output never contains brief text', () => {
  const s = classifyBrief('SECRET-COMPANY-NAME senior product manager');
  assert.ok(!JSON.stringify(s).includes('SECRET'));
});
test('the nine real JDs each get at least one non-unknown label', () => {
  const dir = 'docs/agent-readable/evals/health/jds/';
  const files = ['alan-product-lead-growth.txt', 'danske-genai-lead.txt', 'ghost-application.txt', 'gravy-product.txt',
    'heyra-deployment-strategist.txt', 'lunar-senior-pm-core-experience.txt', 'novonesis-senior-principal-innovation-pm.txt',
    'simcorp-principal-product-owner-ai.txt', 'swordhealth-head-of-product-pulse.txt'];
  for (const f of files) {
    const s = classifyBrief(readFileSync(dir + f, 'utf8'));
    console.log(`     ${f}: ${s.seniority} / ${s.function} / ${s.sector}`);
    assert.ok(Object.values(s).some(v => v !== 'unknown'), f);
  }
});
console.log(`\n${passed} passed`);
