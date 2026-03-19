/**
 * Pretty console output for research results and agent traces.
 */

import type { AgentResult } from "./agent/types.js";

export function displayResult(result: AgentResult): void {
  console.log("\n" + "=".repeat(60));
  console.log("  RESEARCH RESULT");
  console.log("=".repeat(60));

  console.log(`  Goal:       ${result.goal}`);
  console.log(`  Tier:       ${result.tier}`);
  console.log(`  Query:      ${result.query}`);
  console.log(`  Date range: ${result.startDate} to ${result.endDate}`);
  console.log(`  Cost:       ${result.cost}`);
  console.log(`  Status:     ${result.success ? "SUCCESS" : "FAILED"}`);

  if (result.error) {
    console.log(`  Error:      ${result.error}`);
  }

  if (result.summary) {
    console.log("\n--- Summary ---");
    console.log(result.summary);
  }

  if (result.keyFindings && result.keyFindings.length > 0) {
    console.log("\n--- Key Findings ---");
    for (const finding of result.keyFindings) {
      const f = finding as { finding?: string; title?: string; event_type?: string; confidence?: string };
      const text = f.finding ?? f.title ?? "Finding";
      const tag = f.event_type ? ` [${f.event_type}]` : "";
      const conf = f.confidence ? ` (${f.confidence})` : "";
      console.log(`  - ${text}${tag}${conf}`);
    }
  }

  console.log("=".repeat(60) + "\n");
}

export function displayDirectResult(
  tier: string,
  cost: string,
  data: Record<string, unknown>,
): void {
  console.log("\n" + "=".repeat(60));
  console.log("  DIRECT PURCHASE RESULT");
  console.log("=".repeat(60));

  console.log(`  Tier:       ${tier}`);
  console.log(`  Cost:       ${cost}`);
  console.log(`  Status:     ${data.status ?? "unknown"}`);
  console.log(`  Request ID: ${data.request_id ?? "n/a"}`);

  if (data.summary) {
    console.log("\n--- Summary ---");
    console.log(data.summary);
  }

  if (Array.isArray(data.key_findings) && data.key_findings.length > 0) {
    console.log("\n--- Key Findings ---");
    for (const f of data.key_findings) {
      const title = (f as { title?: string }).title ?? "Finding";
      console.log(`  - ${title}`);
    }
  }

  console.log("=".repeat(60) + "\n");
}
