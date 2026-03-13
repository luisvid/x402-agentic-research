import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mkdirSync, rmSync } from "fs";

// Mock logger
vi.mock("../index.js", () => ({
  logger: { info: vi.fn(), debug: vi.fn(), error: vi.fn(), warn: vi.fn() },
}));

import { AuditStore } from "../services/audit-store.js";

const TEST_DB = "data/test-audit.db";

describe("AuditStore", () => {
  let store: AuditStore;

  beforeEach(() => {
    mkdirSync("data", { recursive: true });
    store = new AuditStore(TEST_DB);
  });

  afterEach(() => {
    store.close();
    rmSync(TEST_DB, { force: true });
    rmSync(TEST_DB + "-wal", { force: true });
    rmSync(TEST_DB + "-shm", { force: true });
  });

  it("inserts and retrieves a record", () => {
    store.insert({
      request_id: "test-123",
      query: "Test query for audit",
      tier: "pro",
      quoted_price: "$0.03",
      asset: "USDC",
      network: "base-sepolia",
      payment_status: "mock",
      provider_status: "pending",
      engine_latency_ms: null,
      created_at: new Date().toISOString(),
    });

    const record = store.getByRequestId("test-123");
    expect(record).toBeDefined();
    expect(record!.query).toBe("Test query for audit");
    expect(record!.tier).toBe("pro");
    expect(record!.payment_status).toBe("mock");
    expect(record!.provider_status).toBe("pending");
  });

  it("completes a record with status and latency", () => {
    store.insert({
      request_id: "test-456",
      query: "Another test query",
      tier: "basic",
      quoted_price: "$0.01",
      asset: "USDC",
      network: "base-sepolia",
      payment_status: "paid",
      provider_status: "pending",
      engine_latency_ms: null,
      created_at: new Date().toISOString(),
    });

    store.complete("test-456", "completed", 1500);

    const record = store.getByRequestId("test-456");
    expect(record!.provider_status).toBe("completed");
    expect(record!.engine_latency_ms).toBe(1500);
    expect(record!.completed_at).toBeTruthy();
  });

  it("lists records in reverse chronological order", () => {
    for (let i = 0; i < 3; i++) {
      store.insert({
        request_id: `test-${i}`,
        query: `Query ${i}`,
        tier: "basic",
        quoted_price: "$0.01",
        asset: "USDC",
        network: "base-sepolia",
        payment_status: "mock",
        provider_status: "completed",
        engine_latency_ms: 100 * i,
        created_at: new Date(Date.now() + i * 1000).toISOString(),
      });
    }

    const records = store.getAll(10);
    expect(records).toHaveLength(3);
    // Most recent first
    expect(records[0].request_id).toBe("test-2");
  });

  it("returns undefined for missing record", () => {
    const record = store.getByRequestId("nonexistent");
    expect(record).toBeUndefined();
  });
});
