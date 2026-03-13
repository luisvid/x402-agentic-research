import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock logger before imports
vi.mock("../index.js", () => ({
  logger: { info: vi.fn(), debug: vi.fn(), error: vi.fn(), warn: vi.fn() },
}));

import { executeTool, type ToolContext } from "../agent/tools.js";
import { BudgetTracker } from "../client/budget.js";

function createConfig() {
  return {
    GATEWAY_URL: "http://localhost:8200",
    BUYER_EVM_PRIVATE_KEY: "0x01",
    AGENT_LLM_API_KEY: "",
    AGENT_LLM_MODEL: "claude-sonnet-4-20250514",
    LOG_LEVEL: "info" as const,
    MOCK_MODE: false,
    DAILY_BUDGET_USD: 1.0,
    PER_REQUEST_LIMIT_USD: 0.10,
  };
}

describe("agent tools", () => {
  let ctx: ToolContext;

  beforeEach(() => {
    ctx = {
      client: {} as ToolContext["client"],
      budget: new BudgetTracker(createConfig()),
    };
  });

  it("list_tiers returns all tiers", async () => {
    const result = await executeTool("list_tiers", {}, ctx);
    const parsed = JSON.parse(result);
    expect(parsed.tiers).toHaveLength(3);
    expect(parsed.tiers[0].name).toBe("basic");
    expect(parsed.tiers[1].name).toBe("pro");
    expect(parsed.tiers[2].name).toBe("deep");
  });

  it("check_budget returns allowed for valid tier", async () => {
    const result = await executeTool("check_budget", { tier: "pro" }, ctx);
    const parsed = JSON.parse(result);
    expect(parsed.allowed).toBe(true);
    expect(parsed.price).toBe(0.03);
  });

  it("check_budget rejects over-budget tier", async () => {
    ctx.budget = new BudgetTracker({
      ...createConfig(),
      PER_REQUEST_LIMIT_USD: 0.02,
    });
    const result = await executeTool("check_budget", { tier: "pro" }, ctx);
    const parsed = JSON.parse(result);
    expect(parsed.allowed).toBe(false);
  });

  it("unknown tool returns error", async () => {
    const result = await executeTool("unknown_tool", {}, ctx);
    const parsed = JSON.parse(result);
    expect(parsed.error).toContain("Unknown tool");
  });
});
