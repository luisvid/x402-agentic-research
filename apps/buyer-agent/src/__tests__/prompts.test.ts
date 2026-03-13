import { describe, it, expect } from "vitest";
import { SYSTEM_PROMPT, TOOL_DEFINITIONS } from "../agent/prompts.js";

describe("agent prompts", () => {
  it("system prompt mentions all three tools", () => {
    expect(SYSTEM_PROMPT).toContain("list_tiers");
    expect(SYSTEM_PROMPT).toContain("check_budget");
    expect(SYSTEM_PROMPT).toContain("purchase_research");
  });

  it("tool definitions have correct structure", () => {
    expect(TOOL_DEFINITIONS).toHaveLength(3);

    for (const tool of TOOL_DEFINITIONS) {
      expect(tool).toHaveProperty("name");
      expect(tool).toHaveProperty("description");
      expect(tool).toHaveProperty("input_schema");
      expect(tool.input_schema).toHaveProperty("type", "object");
    }
  });

  it("purchase_research requires all fields", () => {
    const purchase = TOOL_DEFINITIONS.find(
      (t) => t.name === "purchase_research",
    );
    expect(purchase).toBeDefined();
    expect(purchase!.input_schema.required).toContain("query");
    expect(purchase!.input_schema.required).toContain("start_date");
    expect(purchase!.input_schema.required).toContain("end_date");
    expect(purchase!.input_schema.required).toContain("tier");
  });
});
