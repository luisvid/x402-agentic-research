/**
 * SQLite-backed audit store for research run records.
 *
 * Every research request is recorded with payment status, provider status,
 * timing, and metadata for traceability and demo inspection.
 */

import Database from "better-sqlite3";
import { logger } from "../index.js";

export interface RunRecord {
  request_id: string;
  query: string;
  tier: string;
  quoted_price: string;
  asset: string;
  network: string;
  payment_status: "paid" | "mock" | "unpaid";
  provider_status: "completed" | "failed" | "no_data" | "pending";
  engine_latency_ms: number | null;
  created_at: string;
  completed_at: string | null;
  quality_flag: string | null;
}

export class AuditStore {
  private db: Database.Database;

  constructor(dbPath = "data/audit.db") {
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
    this.init();
  }

  private init(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS run_records (
        request_id TEXT PRIMARY KEY,
        query TEXT NOT NULL,
        tier TEXT NOT NULL,
        quoted_price TEXT NOT NULL,
        asset TEXT NOT NULL DEFAULT 'USDC',
        network TEXT NOT NULL DEFAULT 'base-sepolia',
        payment_status TEXT NOT NULL DEFAULT 'pending',
        provider_status TEXT NOT NULL DEFAULT 'pending',
        engine_latency_ms INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT,
        quality_flag TEXT
      )
    `);
    // Migrate existing databases that predate quality_flag column
    try {
      this.db.exec("ALTER TABLE run_records ADD COLUMN quality_flag TEXT");
    } catch {
      // Column already exists — ignore
    }
    logger.info("Audit store initialized");
  }

  insert(record: Omit<RunRecord, "completed_at" | "quality_flag">): void {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO run_records
        (request_id, query, tier, quoted_price, asset, network, payment_status, provider_status, engine_latency_ms, created_at)
      VALUES
        (@request_id, @query, @tier, @quoted_price, @asset, @network, @payment_status, @provider_status, @engine_latency_ms, @created_at)
    `);
    stmt.run(record);
  }

  complete(
    requestId: string,
    status: RunRecord["provider_status"],
    latencyMs: number | null,
  ): void {
    const stmt = this.db.prepare(`
      UPDATE run_records
      SET provider_status = ?, engine_latency_ms = ?, completed_at = datetime('now')
      WHERE request_id = ?
    `);
    stmt.run(status, latencyMs, requestId);
  }

  getAll(limit = 50): RunRecord[] {
    const stmt = this.db.prepare(
      "SELECT * FROM run_records ORDER BY created_at DESC LIMIT ?",
    );
    return stmt.all(limit) as RunRecord[];
  }

  getByRequestId(requestId: string): RunRecord | undefined {
    const stmt = this.db.prepare(
      "SELECT * FROM run_records WHERE request_id = ?",
    );
    return stmt.get(requestId) as RunRecord | undefined;
  }

  flag(requestId: string, reason: string): boolean {
    const stmt = this.db.prepare(
      "UPDATE run_records SET quality_flag = ? WHERE request_id = ?",
    );
    const result = stmt.run(reason, requestId);
    return result.changes > 0;
  }

  close(): void {
    this.db.close();
  }
}
