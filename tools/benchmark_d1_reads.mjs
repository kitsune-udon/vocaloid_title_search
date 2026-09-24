// Called by benchmark_d1_reads.py. Miniflare has no remote D1 binding or credentials.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
const require = createRequire(new URL("../cloudflare/worker/package.json", import.meta.url));
const { Miniflare } = require("miniflare");
const { build } = require("esbuild");
const [directory, output] = process.argv.slice(2);
const root = fileURLToPath(new URL("..", import.meta.url));
function metric(response, name) {
  const value = response.headers.get(name);
  if (value === null || !/^\d+$/.test(value)) throw new Error(`Missing or invalid D1 metric: ${name}`);
  return Number(value);
}
const workers = [];
for (const [name, entry] of [["current", `${root}/cloudflare/worker/src/index.ts`], ["baseline", `${directory}/baseline.ts`]]) {
  const result = await build({ entryPoints: [entry], bundle: true, write: false, format: "esm", platform: "browser" });
  workers.push({ name, modules: true, script: result.outputFiles[0].text,
    compatibilityDate: "2026-06-09", d1Databases: { DB: "benchmark-local" }, bindings: { API_TIMING_LOGS: "0" } });
}
const mf = new Miniflare({ workers });
try {
  const db = await mf.getD1Database("DB", "current");
  const statements = JSON.parse(readFileSync(`${directory}/statements.json`, "utf8"));
  let initialWritten = 0;
  for (let offset = 0; offset < statements.length; offset += 100) {
    const loaded = await db.batch(statements.slice(offset, offset + 100).map(sql => db.prepare(sql)));
    initialWritten += loaded.reduce((sum, result) => sum + result.meta.rows_written, 0);
  }
  const baseline = await mf.getWorker("baseline");
  const current = await mf.getWorker("current");
  const report = { environment: "local Miniflare D1", requests: [], sql: [], writes: [{ scenario: "full publication into empty D1", rows_written: initialWritten }] };
  for (const path of ["/health", "/api/stats", "/api/popularity-labels", "/api/search", "/api/search?length=5",
    "/api/search?composer=ryo", "/api/search?year=2021", "/api/search?sort=published_year_desc", "/api/search?page=20"]) {
    const old = await baseline.fetch(`http://localhost${path}`);
    assert.equal(old.status, 200);
    const expected = await old.json();
    const baselineRows = metric(old, "x-d1-rows-read");
    for (let run = 0; run < 2; run++) {
      const response = await current.fetch(`http://localhost${path}`);
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), expected, `API changed: ${path}`);
      report.requests.push({ path, run, results_equal: true, baseline_rows_read: baselineRows, rows_read: metric(response, "x-d1-rows-read"),
        queries: metric(response, "x-d1-queries"), cache: response.headers.get("x-search-cache") });
    }
  }
  for (const [name, sql] of [
    ["previous readiness songs", "SELECT COUNT(*) AS count FROM songs"],
    ["previous readiness details", "SELECT COUNT(*) AS count FROM song_details"],
    ["previous stats composers", "SELECT COUNT(DISTINCT song_url) FROM song_credit_people WHERE role = 'composer'"],
    ["previous stats lengths", "SELECT title_length, COUNT(*) FROM songs GROUP BY title_length"],
  ]) {
    const result = await db.prepare(sql).all();
    report.sql.push({ name, rows_read: result.meta.rows_read });
  }
  const originalMetadata = (await db.prepare("SELECT key, value FROM metadata ORDER BY key").all()).results;
  const incremental = JSON.parse(readFileSync(`${directory}/incremental.json`, "utf8"));
  for (const direction of ["forward", "rollback"]) {
    const results = await db.batch(incremental[direction].map(sql => db.prepare(sql)));
    report.writes.push({ scenario: `unchanged details metadata refresh ${direction}`,
      rows_written: results.reduce((sum, result) => sum + result.meta.rows_written, 0) });
  }
  assert.deepEqual((await db.prepare("SELECT key, value FROM metadata ORDER BY key").all()).results, originalMetadata);
  writeFileSync(output, JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report, null, 2));
} finally { await mf.dispose(); }
