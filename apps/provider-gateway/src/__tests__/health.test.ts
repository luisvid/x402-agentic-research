import { describe, it, expect } from "vitest";

describe("provider-gateway", () => {
  it("config loads with defaults", async () => {
    const { loadConfig } = await import("../config.js");
    const config = loadConfig();
    expect(config.PORT).toBe(8200);
    expect(config.MOCK_MODE).toBe(false);
  });

  it("tier schema validates correctly", async () => {
    const { tierSchema } = await import("../schemas/research.js");
    expect(tierSchema.safeParse("pro").success).toBe(true);
    expect(tierSchema.safeParse("invalid").success).toBe(false);
  });

  it("research request schema validates", async () => {
    const { researchRequestSchema } = await import("../schemas/research.js");
    const valid = researchRequestSchema.safeParse({
      query: "Why did Ethena TVL drop significantly?",
      start_date: "2025-10-01",
      end_date: "2026-03-01",
    });
    expect(valid.success).toBe(true);

    const invalid = researchRequestSchema.safeParse({
      query: "short",
      start_date: "bad-date",
      end_date: "2026-03-01",
    });
    expect(invalid.success).toBe(false);
  });
});
