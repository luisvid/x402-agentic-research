import { describe, it, expect } from "vitest";

describe("buyer-agent", () => {
  it("config loads with defaults", async () => {
    const { loadConfig } = await import("../config.js");
    const config = loadConfig();
    expect(config.GATEWAY_URL).toBe("http://localhost:8200");
    expect(config.DAILY_BUDGET_USD).toBe(1.0);
    expect(config.MOCK_MODE).toBe(false);
  });
});
