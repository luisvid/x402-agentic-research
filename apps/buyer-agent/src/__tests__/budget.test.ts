import { describe, it, expect, vi } from "vitest";

// Mock logger to prevent index.ts side effects (commander parse)
vi.mock("../index.js", () => ({
  logger: { info: vi.fn(), debug: vi.fn(), error: vi.fn(), warn: vi.fn() },
}));

import { BudgetTracker } from "../client/budget.js";

function createConfig(overrides: Record<string, unknown> = {}) {
  return {
    GATEWAY_URL: "http://localhost:8200",
    BUYER_EVM_PRIVATE_KEY: "0x01",
    AGENT_LLM_API_KEY: "",
    AGENT_LLM_MODEL: "claude-sonnet-4-20250514",
    LOG_LEVEL: "info" as const,
    MOCK_MODE: false,
    DAILY_BUDGET_USD: 0.10,
    PER_REQUEST_LIMIT_USD: 0.05,
    ...overrides,
  };
}

describe("BudgetTracker", () => {
  it("allows purchase within limits", () => {
    const budget = new BudgetTracker(createConfig());
    const check = budget.checkBudget("basic");
    expect(check.allowed).toBe(true);
  });

  it("rejects unknown tier", () => {
    const budget = new BudgetTracker(createConfig());
    const check = budget.checkBudget("platinum");
    expect(check.allowed).toBe(false);
    expect(check.reason).toContain("Unknown tier");
  });

  it("rejects tier exceeding per-request limit", () => {
    const budget = new BudgetTracker(
      createConfig({ PER_REQUEST_LIMIT_USD: 0.02 }),
    );
    const check = budget.checkBudget("pro"); // $0.03
    expect(check.allowed).toBe(false);
    expect(check.reason).toContain("per-request limit");
  });

  it("rejects when daily budget exhausted", () => {
    const budget = new BudgetTracker(
      createConfig({ DAILY_BUDGET_USD: 0.04, PER_REQUEST_LIMIT_USD: 0.05 }),
    );
    // Spend $0.03
    budget.recordSpend("pro");
    // Now $0.03 left in budget is < daily limit, trying another pro ($0.03) should fail
    const check = budget.checkBudget("pro");
    expect(check.allowed).toBe(false);
    expect(check.reason).toContain("Daily budget exhausted");
  });

  it("tracks spending correctly", () => {
    const budget = new BudgetTracker(createConfig());
    budget.recordSpend("basic"); // $0.01
    budget.recordSpend("pro"); // $0.03
    const status = budget.getStatus();
    expect(status.dailySpent).toBeCloseTo(0.04);
    expect(status.remaining).toBeCloseTo(0.06);
  });

  it("returns tier price", () => {
    expect(BudgetTracker.getTierPrice("basic")).toBe(0.01);
    expect(BudgetTracker.getTierPrice("pro")).toBe(0.03);
    expect(BudgetTracker.getTierPrice("deep")).toBe(0.05);
    expect(BudgetTracker.getTierPrice("unknown")).toBeUndefined();
  });
});
