export interface Env {
  DB: D1Database;
  CORS_ORIGINS?: string;
  API_TIMING_LOGS?: string;
}

export interface D1Database {
  prepare(query: string): D1PreparedStatement;
  batch<T = unknown>(statements: D1PreparedStatement[]): Promise<Array<D1Result<T>>>;
}

export interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  first<T = unknown>(): Promise<T | null>;
  all<T = unknown>(): Promise<D1Result<T>>;
}

export interface D1Result<T = unknown> {
  meta?: { rows_read?: number };
  results?: T[];
}

export interface ReadMetrics { queries: number; rowsRead: number; complete: boolean }

export function observeDatabase(db: D1Database, metrics: ReadMetrics): D1Database {
  const originals = new WeakMap<D1PreparedStatement, D1PreparedStatement>();
  const record = <T>(result: D1Result<T>): D1Result<T> => {
    const count = result.meta?.rows_read;
    if (typeof count === "number" && Number.isFinite(count) && count >= 0) metrics.rowsRead += count;
    else metrics.complete = false;
    return result;
  };
  const wrap = (statement: D1PreparedStatement): D1PreparedStatement => {
    const wrapped: D1PreparedStatement = {
      bind: (...values) => wrap(statement.bind(...values)),
      async all<T>() {
        metrics.queries++;
        try { return record(await statement.all<T>()); }
        catch (error) { metrics.complete = false; throw error; }
      },
      async first<T>() { return (await wrapped.all<T>()).results?.[0] ?? null; },
    };
    originals.set(wrapped, statement);
    return wrapped;
  };
  return {
    prepare: (query) => wrap(db.prepare(query)),
    async batch<T>(statements: D1PreparedStatement[]) {
      metrics.queries += statements.length;
      try { return (await db.batch<T>(statements.map(statement => originals.get(statement)!))).map(record); }
      catch (error) { metrics.complete = false; throw error; }
    },
  };
}
