/**
 * LLM-powered research agent — uses Anthropic tool-calling to orchestrate
 * tier selection, budget checks, and research purchases.
 */

import Anthropic from "@anthropic-ai/sdk";
import type { AxiosInstance } from "axios";
import type { Config } from "../config.js";
import type { AgentResult } from "./types.js";
import { SYSTEM_PROMPT, TOOL_DEFINITIONS } from "./prompts.js";
import { executeTool, type ToolContext } from "./tools.js";
import { BudgetTracker } from "../client/budget.js";
import { logger } from "../index.js";

const MAX_TURNS = 10;

export async function runResearchAgent(
  goal: string,
  config: Config,
  client: AxiosInstance,
): Promise<AgentResult> {
  const anthropic = new Anthropic({ apiKey: config.AGENT_LLM_API_KEY });
  const budget = new BudgetTracker(config);

  const toolCtx: ToolContext = { client, budget };

  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: goal },
  ];

  let lastResult: AgentResult = {
    goal,
    tier: "",
    query: "",
    startDate: "",
    endDate: "",
    summary: null,
    keyFindings: null,
    cost: "$0.00",
    success: false,
    error: "Agent did not complete",
  };

  for (let turn = 0; turn < MAX_TURNS; turn++) {
    logger.info({ turn, messageCount: messages.length }, "Agent turn");

    const response = await anthropic.messages.create({
      model: config.AGENT_LLM_MODEL,
      max_tokens: 4096,
      system: SYSTEM_PROMPT,
      tools: TOOL_DEFINITIONS as unknown as Anthropic.Tool[],
      messages,
    });

    logger.debug(
      { stopReason: response.stop_reason, contentBlocks: response.content.length },
      "LLM response",
    );

    // If the model stops without tool use, we're done
    if (response.stop_reason === "end_turn") {
      const textBlock = response.content.find((b) => b.type === "text");
      const text = textBlock && "text" in textBlock ? textBlock.text : "";
      lastResult = {
        ...lastResult,
        summary: text,
        success: true,
        cost: formatCost(budget),
      };
      // Add assistant message for display purposes
      messages.push({ role: "assistant", content: response.content });
      break;
    }

    // Process tool use blocks
    if (response.stop_reason === "tool_use") {
      const toolUseBlocks = response.content.filter(
        (b) => b.type === "tool_use",
      );

      // Add assistant message with tool_use content
      messages.push({ role: "assistant", content: response.content });

      const toolResults: Anthropic.ToolResultBlockParam[] = [];

      for (const block of toolUseBlocks) {
        if (block.type !== "tool_use") continue;

        logger.info(
          { tool: block.name, input: block.input },
          "Executing tool",
        );

        const result = await executeTool(
          block.name,
          block.input as Record<string, unknown>,
          toolCtx,
        );

        logger.debug({ tool: block.name, resultLen: result.length }, "Tool result");

        // Track purchase details for the final result
        if (block.name === "purchase_research") {
          const input = block.input as {
            query: string;
            start_date: string;
            end_date: string;
            tier: string;
          };
          const parsed = JSON.parse(result);
          lastResult = {
            ...lastResult,
            tier: input.tier,
            query: input.query,
            startDate: input.start_date,
            endDate: input.end_date,
            keyFindings: parsed.key_findings ?? null,
            cost: formatCost(budget),
            success: parsed.success ?? false,
          };
        }

        toolResults.push({
          type: "tool_result",
          tool_use_id: block.id,
          content: result,
        });
      }

      messages.push({ role: "user", content: toolResults });
    }
  }

  return lastResult;
}

function formatCost(budget: BudgetTracker): string {
  return `$${budget.getStatus().dailySpent.toFixed(2)}`;
}
