/**
 * Agent tool implementations — bridge between LLM tool calls and actual operations.
 */

import type { AxiosInstance } from "axios";
import { TIERS } from "./types.js";
import { BudgetTracker } from "../client/budget.js";
import { purchaseResearch } from "../client/x402-client.js";
import { logger } from "../index.js";

export interface ToolContext {
  client: AxiosInstance;
  budget: BudgetTracker;
}

export async function executeTool(
  name: string,
  input: Record<string, unknown>,
  ctx: ToolContext,
): Promise<string> {
  switch (name) {
    case "list_tiers":
      return handleListTiers();
    case "check_budget":
      return handleCheckBudget(input as { tier: string }, ctx);
    case "purchase_research":
      return await handlePurchaseResearch(
        input as {
          query: string;
          start_date: string;
          end_date: string;
          tier: string;
        },
        ctx,
      );
    default:
      return JSON.stringify({ error: `Unknown tool: ${name}` });
  }
}

function handleListTiers(): string {
  return JSON.stringify({ tiers: TIERS }, null, 2);
}

function handleCheckBudget(
  input: { tier: string },
  ctx: ToolContext,
): string {
  const check = ctx.budget.checkBudget(input.tier);
  const status = ctx.budget.getStatus();
  const price = BudgetTracker.getTierPrice(input.tier);
  return JSON.stringify({ ...check, price: price ?? null, budgetStatus: status }, null, 2);
}

async function handlePurchaseResearch(
  input: { query: string; start_date: string; end_date: string; tier: string },
  ctx: ToolContext,
): Promise<string> {
  // Pre-check budget
  const budgetCheck = ctx.budget.checkBudget(input.tier);
  if (!budgetCheck.allowed) {
    return JSON.stringify({ success: false, error: budgetCheck.reason });
  }

  try {
    const result = await purchaseResearch(ctx.client, input.tier, {
      query: input.query,
      start_date: input.start_date,
      end_date: input.end_date,
    });

    ctx.budget.recordSpend(input.tier);

    return JSON.stringify(
      {
        success: true,
        request_id: result.request_id,
        status: result.status,
        tier: result.tier,
        summary: result.summary,
        key_findings: result.key_findings,
        confidence: result.confidence,
        report_markdown: result.report_markdown,
      },
      null,
      2,
    );
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Unknown error during purchase";
    logger.error({ err, tier: input.tier }, "Research purchase failed");
    return JSON.stringify({ success: false, error: message });
  }
}
