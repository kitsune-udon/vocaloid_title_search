import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { before, describe, it } from "node:test";
import { build } from "esbuild";

let worker;

before(async () => {
  const output = join(tmpdir(), `vocaloid-worker-${Date.now()}`, "index.mjs");
  mkdirSync(join(output, ".."), { recursive: true });
  await build({
    entryPoints: ["src/index.ts"],
    outfile: output,
    bundle: true,
    format: "esm",
    platform: "browser",
    logLevel: "silent",
  });
  worker = (await import(pathToFileURL(output).href)).default;
});

describe("Worker API", () => {
  it("reports health and database readiness", async () => {
    const response = await request("/health", env());

    assert.equal(response.status, 200);
    assertSecurityHeaders(response);
    assert.deepEqual(await response.json(), { ok: true, database_ready: true });
  });

  it("returns database not ready for metadata when details are incomplete", async () => {
    const fixture = fixtureData();
    fixture.details.pop();
    const response = await request("/api/metadata", env(fixture));

    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { detail: "database is not ready" });
  });

  it("reports database not ready when required metadata is missing", async () => {
    const fixture = fixtureData();
    delete fixture.metadata.detail_count;
    const healthResponse = await request("/health", env(fixture));
    const metadataResponse = await request("/api/metadata", env(fixture));

    assert.equal(healthResponse.status, 200);
    assert.deepEqual(await healthResponse.json(), { ok: true, database_ready: false });
    assert.equal(metadataResponse.status, 503);
    assert.deepEqual(await metadataResponse.json(), { detail: "database is not ready" });
  });

  it("reports database not ready when metadata counts do not match tables", async () => {
    const fixture = fixtureData();
    fixture.metadata.song_count = "999";
    const response = await request("/health", env(fixture));

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { ok: true, database_ready: false });
  });

  it("handles CORS preflight for configured origins", async () => {
    const response = await request("/api/metadata", env(), {
      method: "OPTIONS",
      headers: { origin: "http://127.0.0.1:5173" },
    });

    assert.equal(response.status, 204);
    assertSecurityHeaders(response);
    assert.equal(response.headers.get("access-control-allow-origin"), "http://127.0.0.1:5173");
    assert.equal(response.headers.get("access-control-allow-methods"), "GET, OPTIONS");
  });

  it("rejects non-GET methods", async () => {
    const response = await request("/api/metadata", env(), { method: "POST" });

    assert.equal(response.status, 405);
    assert.deepEqual(await response.json(), { detail: "method not allowed" });
  });

  it("returns metadata and popularity labels", async () => {
    const metadata = await jsonRequest("/api/metadata");
    const labels = await jsonRequest("/api/popularity-labels");

    assert.equal(metadata.schema_version, "7");
    assert.equal(metadata.song_count, "3");
    assert.deepEqual(labels.labels, ["テンミリオン達成曲", "ミリオン達成曲", "殿堂入り"]);
  });

  it("searches by title length, composer, year, popularity label, and pagination", async () => {
    const data = await jsonRequest(
      "/api/search?length=3&composer=RYO&year=2007&popularity_label=テンミリオン達成曲&page=1&page_size=50",
    );

    assert.equal(data.total, 1);
    assert.equal(data.page, 1);
    assert.equal(data.page_size, 50);
    assert.equal(data.results[0].title, "メルト");
    assert.equal(data.results[0].artist, "ryo");
    assert.equal(data.results[0].published_year, 2007);
  });

  it("sorts search results by title length descending", async () => {
    const data = await jsonRequest("/api/search?sort=title_length_desc&page_size=50");

    assert.deepEqual(data.results.map((row) => row.title), ["長い曲名", "メルト", "短曲"]);
  });

  it("rejects invalid search parameters", async () => {
    const invalidSort = await request("/api/search?sort=wiki", env());
    const invalidPageSize = await request("/api/search?page_size=25", env());
    const invalidLabel = await request("/api/search?popularity_label=未知", env());
    const invalidLength = await request("/api/search?length=abc", env());
    const invalidPage = await request("/api/search?page=0", env());

    assert.equal(invalidSort.status, 400);
    assert.equal((await invalidSort.json()).detail, "sort is not supported");
    assert.equal(invalidPageSize.status, 400);
    assert.equal((await invalidPageSize.json()).detail, "page_size must be one of 50, 100, 200");
    assert.equal(invalidLabel.status, 400);
    assert.equal((await invalidLabel.json()).detail, "invalid popularity_label");
    assert.equal(invalidLength.status, 400);
    assert.equal((await invalidLength.json()).detail, "length must be an integer");
    assert.equal(invalidPage.status, 400);
    assert.equal((await invalidPage.json()).detail, "page must be 1 or greater");
  });

  it("returns stored song detail and validates wiki URLs", async () => {
    const detail = await jsonRequest("/api/song-detail?url=https%3A%2F%2Fw.atwiki.jp%2Fhmiku%2Fpages%2F82.html");
    const invalid = await request("/api/song-detail?url=https%3A%2F%2Fexample.com%2F82.html", env());
    const missing = await request("/api/song-detail?url=https%3A%2F%2Fw.atwiki.jp%2Fhmiku%2Fpages%2F999.html", env());

    assert.equal(detail.page_title, "メルト");
    assert.equal(invalid.status, 400);
    assert.equal((await invalid.json()).detail, "invalid wiki url");
    assert.equal(missing.status, 404);
    assert.equal((await missing.json()).detail, "song detail is not available");
  });

  it("returns statistics", async () => {
    const stats = await jsonRequest("/api/stats");

    assert.equal(stats.total_songs, 3);
    assert.equal(stats.detail_count, 3);
    assert.equal(stats.with_composer, 2);
    assert.equal(stats.with_published_year, 3);
    assert.deepEqual(stats.by_title_length, [
      { length: 2, count: 1 },
      { length: 3, count: 1 },
      { length: 4, count: 1 },
    ]);
    assert.deepEqual(
      stats.top_composers.map((row) => [row.name, row.count]).sort(),
      [["Neru", 1], ["ryo", 1]],
    );
  });

  it("uses readiness metadata counts for statistics totals", async () => {
    const testEnv = env();
    const response = await request("/api/stats", testEnv);

    assert.equal(response.status, 200);
    assert.equal(countPreparedQueries(testEnv.DB, "SELECT COUNT(*) AS count FROM songs"), 1);
    assert.equal(countPreparedQueries(testEnv.DB, "SELECT COUNT(*) AS count FROM song_details"), 1);
  });

  it("returns not found for unknown routes", async () => {
    const response = await request("/api/unknown", env());

    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), { detail: "not found" });
  });

  it("logs API timing when enabled", async () => {
    const logs = [];
    const originalLog = console.log;
    console.log = (message) => logs.push(String(message));
    try {
      const response = await request("/api/search?length=3", envWithTimingLogs());
      assert.equal(response.status, 200);
    } finally {
      console.log = originalLog;
    }

    const timing = logs.map((line) => JSON.parse(line)).find((entry) => entry.event === "api_timing");
    assert.equal(timing.path, "/api/search");
    assert.equal(timing.method, "GET");
    assert.equal(timing.status, 200);
    assert.equal(typeof timing.duration_ms, "number");
  });
});

async function jsonRequest(path, testEnv = env()) {
  const response = await request(path, testEnv);
  assert.equal(response.status, 200);
  assertSecurityHeaders(response);
  assert.match(response.headers.get("content-type") ?? "", /^application\/json/);
  return response.json();
}

function assertSecurityHeaders(response) {
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
  assert.equal(response.headers.get("permissions-policy"), "camera=(), microphone=(), geolocation=()");
}

async function request(path, testEnv, init = {}) {
  return worker.fetch(new Request(`https://example.test${path}`, init), testEnv);
}

function env(data = fixtureData()) {
  return {
    DB: new FakeD1Database(data),
    CORS_ORIGINS: "http://127.0.0.1:5173,https://vocaloid-title-search.example.com",
    API_TIMING_LOGS: "0",
  };
}

function envWithTimingLogs(data = fixtureData()) {
  return {
    ...env(data),
    API_TIMING_LOGS: "1",
  };
}

function fixtureData() {
  return {
    metadata: {
      schema_version: "7",
      fetched_at: "2026-06-09T00:00:00+00:00",
      song_count: "3",
      title_length_rule: "unicode_nfc_grapheme_cluster_whitespace_excluded",
      detail_schema_version: "1",
      detail_count: "3",
    },
    songs: [
      song("メルト", 3, "https://w.atwiki.jp/hmiku/pages/82.html", 1000, "テンミリオン達成曲", 1),
      song("短曲", 2, "https://w.atwiki.jp/hmiku/pages/83.html", 100, "殿堂入り", 3),
      song("長い曲名", 4, "https://w.atwiki.jp/hmiku/pages/84.html", 600, "ミリオン達成曲", 2),
    ],
    details: [
      detail("https://w.atwiki.jp/hmiku/pages/82.html", "メルト", 2007),
      detail("https://w.atwiki.jp/hmiku/pages/83.html", "短曲", 2020),
      detail("https://w.atwiki.jp/hmiku/pages/84.html", "長い曲名", 2024),
    ],
    people: [
      person("https://w.atwiki.jp/hmiku/pages/82.html", "composer", "ryo"),
      person("https://w.atwiki.jp/hmiku/pages/84.html", "composer", "Neru"),
    ],
  };
}

function song(title, length, url, score, label, order) {
  return {
    title,
    title_length: length,
    artist: "",
    artist_note: "",
    song_url: url,
    popularity_score: score,
    popularity_label: label,
    popularity_order: order,
    sort_order: order,
  };
}

function detail(url, pageTitle, year) {
  return {
    url,
    published_year: year,
    payload_json: JSON.stringify({
      page_title: pageTitle,
      source_url: url,
      published_year: year,
      credits: {},
      videos: { niconico: [], youtube: [] },
      related_videos: { niconico: [], youtube: [] },
    }),
  };
}

function person(url, role, name) {
  return {
    song_url: url,
    role,
    name,
    normalized_name: name.normalize("NFKC").toLocaleLowerCase().trim(),
  };
}

class FakeD1Database {
  constructor(data) {
    this.data = data;
    this.queries = [];
  }

  prepare(query) {
    this.queries.push(compactSql(query));
    return new FakeD1PreparedStatement(this, query);
  }

  async batch(statements) {
    return Promise.all(statements.map((statement) => statement.all()));
  }
}

function countPreparedQueries(db, query) {
  return db.queries.filter((preparedQuery) => preparedQuery === query).length;
}

class FakeD1PreparedStatement {
  constructor(db, query) {
    this.db = db;
    this.query = query;
    this.values = [];
  }

  bind(...values) {
    this.values = values;
    return this;
  }

  async first() {
    const result = await this.all();
    return result.results[0] ?? null;
  }

  async all() {
    const query = compactSql(this.query);
    const data = this.db.data;

    if (query === "SELECT key, value FROM metadata") {
      return rows(Object.entries(data.metadata).map(([key, value]) => ({ key, value })));
    }
    if (query === "SELECT COUNT(*) AS count FROM songs") {
      return rows([{ count: data.songs.length }]);
    }
    if (query === "SELECT COUNT(*) AS count FROM song_details") {
      return rows([{ count: data.details.length }]);
    }
    if (query.includes("COUNT(*) AS count FROM song_details WHERE published_year IS NOT NULL")) {
      return rows([{ count: data.details.filter((row) => row.published_year !== null && row.published_year !== undefined).length }]);
    }
    if (query.includes("SELECT popularity_label FROM songs")) {
      return rows(popularityLabels(data));
    }
    if (query.includes("SELECT MIN(name) AS name, COUNT(DISTINCT song_url) AS count")) {
      return rows(topComposers(data));
    }
    if (query.includes("COUNT(DISTINCT song_url) AS count FROM song_credit_people WHERE role = 'composer'")) {
      return rows([{ count: new Set(data.people.filter((row) => row.role === "composer").map((row) => row.song_url)).size }]);
    }
    if (query.includes("SELECT title_length AS length, COUNT(*) AS count FROM songs")) {
      return rows(groupCount(data.songs, "title_length", "length").sort((a, b) => a.length - b.length));
    }
    if (query.includes("SELECT published_year AS year, COUNT(*) AS count FROM song_details")) {
      return rows(groupCount(data.details.filter((row) => row.published_year != null), "published_year", "year").sort((a, b) => a.year - b.year));
    }
    if (query.includes("SELECT popularity_label AS label, COUNT(*) AS count FROM songs")) {
      return rows(popularityLabels(data).map((row) => ({
        label: row.popularity_label,
        count: data.songs.filter((songRow) => songRow.popularity_label === row.popularity_label).length,
      })));
    }
    if (query.includes("SELECT COUNT(*) AS count FROM songs JOIN song_details")) {
      return rows([{ count: joinedRows(data, query, this.values).length }]);
    }
    if (query.includes("SELECT songs.title,")) {
      const limit = Number(this.values.at(-2));
      const offset = Number(this.values.at(-1));
      return rows(sortSearchRows(joinedRows(data, query, this.values.slice(0, -2)), query).slice(offset, offset + limit));
    }
    if (query.includes("SELECT payload_json FROM song_details WHERE url = ?")) {
      const found = data.details.find((row) => row.url === this.values[0]);
      return rows(found ? [{ payload_json: found.payload_json }] : []);
    }

    throw new Error(`Unhandled fake D1 query: ${query}`);
  }
}

function rows(results) {
  return { results };
}

function compactSql(sql) {
  return sql.replace(/\s+/g, " ").trim();
}

function groupCount(items, sourceKey, targetKey) {
  const counts = new Map();
  for (const item of items) {
    const value = item[sourceKey];
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return Array.from(counts, ([value, count]) => ({ [targetKey]: value, count }));
}

function popularityLabels(data) {
  const maxScores = new Map();
  for (const row of data.songs) {
    if (!row.popularity_label) continue;
    maxScores.set(row.popularity_label, Math.max(maxScores.get(row.popularity_label) ?? -Infinity, row.popularity_score));
  }
  return Array.from(maxScores, ([popularity_label, maxScore]) => ({ popularity_label, maxScore }))
    .sort((a, b) => b.maxScore - a.maxScore || a.popularity_label.localeCompare(b.popularity_label))
    .map(({ popularity_label }) => ({ popularity_label }));
}

function joinedRows(data, query, values) {
  const conditions = parseSearchConditions(query, values);
  return data.songs
    .map((songRow) => {
      const detailRow = data.details.find((candidate) => candidate.url === songRow.song_url);
      if (!detailRow) return null;
      const composerNames = data.people
        .filter((personRow) => personRow.song_url === songRow.song_url && personRow.role === "composer")
        .map((personRow) => personRow.name)
        .sort()
        .join(" / ");
      return {
        title: songRow.title,
        title_length: songRow.title_length,
        artist: composerNames,
        artist_note: songRow.artist_note,
        url: songRow.song_url,
        popularity_score: songRow.popularity_score,
        popularity_label: songRow.popularity_label,
        popularity_order: songRow.popularity_order,
        sort_order: songRow.sort_order,
        published_year: detailRow.published_year,
      };
    })
    .filter(Boolean)
    .filter((row) => matchesSearch(row, data.people, conditions));
}

function parseSearchConditions(query, values) {
  let index = 0;
  const conditions = {};
  if (query.includes("songs.title_length = ?")) {
    conditions.length = values[index++];
  }
  const labelMatch = query.match(/songs\.popularity_label IN \(([^)]*)\)/);
  if (labelMatch) {
    const labelCount = labelMatch[1].split("?").length - 1;
    conditions.labels = values.slice(index, index + labelCount);
    index += labelCount;
  }
  if (query.includes("song_details.published_year = ?")) {
    conditions.year = values[index++];
  }
  if (query.includes("person.normalized_name LIKE ?")) {
    conditions.composer = String(values[index++] ?? "").replace(/^%|%$/g, "").replace(/\\([%_\\])/g, "$1");
  }
  return conditions;
}

function matchesSearch(row, people, conditions) {
  if (conditions.length !== undefined && row.title_length !== conditions.length) return false;
  if (conditions.labels && !conditions.labels.includes(row.popularity_label)) return false;
  if (conditions.year !== undefined && row.published_year !== conditions.year) return false;
  if (conditions.composer) {
    return people.some((personRow) =>
      personRow.song_url === row.url
      && personRow.role === "composer"
      && personRow.normalized_name.includes(conditions.composer),
    );
  }
  return true;
}

function sortSearchRows(rowsToSort, query) {
  const rowsCopy = [...rowsToSort];
  if (query.includes("title_length DESC")) {
    return rowsCopy.sort((a, b) =>
      b.title_length - a.title_length
      || b.popularity_score - a.popularity_score
      || a.popularity_order - b.popularity_order
      || a.sort_order - b.sort_order,
    );
  }
  if (query.includes("title_length ASC")) {
    return rowsCopy.sort((a, b) =>
      a.title_length - b.title_length
      || b.popularity_score - a.popularity_score
      || a.popularity_order - b.popularity_order
      || a.sort_order - b.sort_order,
    );
  }
  if (query.includes("published_year DESC")) {
    return rowsCopy.sort((a, b) => (b.published_year ?? -Infinity) - (a.published_year ?? -Infinity));
  }
  if (query.includes("published_year ASC")) {
    return rowsCopy.sort((a, b) => (a.published_year ?? Infinity) - (b.published_year ?? Infinity));
  }
  return rowsCopy.sort((a, b) =>
    b.popularity_score - a.popularity_score
    || a.popularity_order - b.popularity_order
    || a.sort_order - b.sort_order,
  );
}

function topComposers(data) {
  const grouped = new Map();
  for (const row of data.people.filter((personRow) => personRow.role === "composer")) {
    const current = grouped.get(row.normalized_name) ?? { name: row.name, urls: new Set() };
    current.name = current.name.localeCompare(row.name) <= 0 ? current.name : row.name;
    current.urls.add(row.song_url);
    grouped.set(row.normalized_name, current);
  }
  return Array.from(grouped.values())
    .map((row) => ({ name: row.name, count: row.urls.size }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .slice(0, 30);
}
