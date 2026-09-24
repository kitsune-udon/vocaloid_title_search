// Exercise production lock SQL on isolated Miniflare D1, without remote bindings.
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
const require = createRequire(new URL('../cloudflare/worker/package.json', import.meta.url));
const { Miniflare } = require('miniflare');
const root = fileURLToPath(new URL('..', import.meta.url));
const sql = JSON.parse(execFileSync('python3', ['-c', `
import json
from tools.d1_update_lock import CREATE, statement
owners = ['00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002']
print(json.dumps({'create':CREATE, 'acquire':[statement('acquire',o) for o in owners], 'release':[statement('release',o) for o in owners]}))
`], { cwd: root, encoding: 'utf8' }));
const mf = new Miniflare({modules: true, script: 'export default {fetch(){return new Response("local")}}',
  compatibilityDate: '2026-06-09', d1Databases: { DB: 'lock-test-local' }});
try {
  const db = await mf.getD1Database('DB');
  await db.prepare(sql.create).run();
  const attempts = await Promise.allSettled(sql.acquire.map(query => db.prepare(query).all()));
  assert.equal(attempts.filter(result => result.status === 'fulfilled').length, 1);
  assert.equal(attempts.filter(result => result.status === 'rejected').length, 1);
  const winner = attempts.findIndex(result => result.status === 'fulfilled');
  const loser = 1 - winner;
  assert.deepEqual((await db.prepare(sql.release[loser]).all()).results, []);
  await assert.rejects(db.prepare(sql.acquire[loser]).all());
  assert.equal((await db.prepare(sql.release[winner]).all()).results.length, 1);
  assert.equal((await db.prepare(sql.acquire[loser]).all()).results.length, 1);
  console.log(JSON.stringify({ok:true,environment:'local Miniflare D1',concurrentWinners:1,foreignReleaseRejected:true,explicitRecovery:true}));
} finally { await mf.dispose(); }
