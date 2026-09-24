import type { StatisticsResponse } from "../../../shared/api-types";
import type { D1Database } from "./database";
import { HttpError, serializeError } from "./http";
const REQUIRED_METADATA_KEYS = [
  "schema_version",
  "fetched_at",
  "song_count",
  "title_length_rule",
  "detail_count",
  "detail_schema_version",
];
const DATABASE_SCHEMA_VERSION = "7";
const DETAIL_SCHEMA_VERSION = "1";
export interface Publication {
  version: number;
  revision: string;
  metadata: Record<string, string>;
  statistics: StatisticsResponse;
}

export async function databaseIsReady(db: D1Database): Promise<boolean> {
  return (await databaseReadiness(db)).ready;
}

async function databaseReadiness(db: D1Database): Promise<{ ready: boolean; publication?: Publication }> {
  try {
    const row = await db.prepare("SELECT value FROM metadata WHERE key = 'api_publication_v1'").first<{ value: string }>();
    if (!row) return { ready: false };
    const publication = JSON.parse(row.value) as Publication;
    const metadata = publication.metadata;
    const stats = publication.statistics;
    const count = Number(metadata.song_count);
    const ready = publication.version === 1 && /^[a-f0-9]{32}$/.test(publication.revision)
      && REQUIRED_METADATA_KEYS.every(key => typeof metadata[key] === "string")
      && metadata.schema_version === DATABASE_SCHEMA_VERSION
      && metadata.detail_schema_version === DETAIL_SCHEMA_VERSION
      && Number.isSafeInteger(count) && count > 0 && Number(metadata.detail_count) === count
      && stats.total_songs === count && stats.detail_count === count
      && [stats.by_title_length, stats.by_published_year, stats.by_popularity_label, stats.top_composers].every(Array.isArray);
    return { ready, publication };
  } catch (error) {
    console.error(JSON.stringify({ event: "database_readiness_error", error: serializeError(error) }));
    return { ready: false };
  }
}

export async function requireDatabaseReady(db: D1Database): Promise<Publication> {
  const readiness = await databaseReadiness(db);
  if (!readiness.ready || !readiness.publication) throw new HttpError(503, "database is not ready");
  return readiness.publication;
}

export async function requireSamePublication(db: D1Database, revision: string): Promise<void> {
  if ((await requireDatabaseReady(db)).revision !== revision) throw new HttpError(503, "database is being updated");
}
