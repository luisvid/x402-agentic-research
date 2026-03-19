/**
 * LLM-powered research agent — uses OpenAI-compatible (GEIA) tool-calling
 * to orchestrate tier selection, budget checks, and research purchases.
 */

import OpenAI from "openai";
import type { AxiosInstance } from "axios";
import type { Config } from "../config.js";
import type { AgentResult } from "./types.js";
import { SYSTEM_PROMPT, TOOL_DEFINITIONS_OPENAI } from "./prompts.js";
import { executeTool, type ToolContext } from "./tools.js";
import { BudgetTracker } from "../client/budget.js";
import { logger } from "../index.js";

const MAX_TURNS = 10;

export async function runResearchAgent(
  goal: string,
  config: Config,
  client: AxiosInstance,
): Promise<AgentResult> {
  const openai = new OpenAI({
    apiKey: config.GEIA_API_KEY,
    baseURL: config.GEIA_API_BASE,
  });
  const budget = new BudgetTracker(config);

  const toolCtx: ToolContext = { client, budget };

  const messages: OpenAI.ChatCompletionMessageParam[] = [
    { role: "system", content: SYSTEM_PROMPT },
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

    const response = await openai.chat.completions.create({
      model: config.BUYER_LLM_MODEL,
      max_tokens: 4096,
      tools: TOOL_DEFINITIONS_OPENAI,
      messages,
    });

    const choice = response.choices[0];
    const message = choice.message;

    logger.debug(
      { finishReason: choice.finish_reason, hasToolCalls: !!message.tool_calls?.length },
      "LLM response",
    );

    // If the model stops without tool use, we're done
    if (choice.finish_reason === "stop") {
      const text = message.content ?? "";
      lastResult = {
        ...lastResult,
        summary: text,
        success: true,
        error: undefined,
        cost: formatCost(budget),
      };
      messages.push(message);
      break;
    }

    // Process tool calls
    if (choice.finish_reason === "tool_calls" && message.tool_calls?.length) {
      messages.push(message);

      for (const toolCall of message.tool_calls) {
        if (toolCall.type !== "function") continue;
        const toolName = toolCall.function.name;
        const toolInput = JSON.parse(toolCall.function.arguments);

        logger.info(
          { tool: toolName, input: toolInput },
          "Executing tool",
        );

        const result = await executeTool(
          toolName,
          toolInput as Record<string, unknown>,
          toolCtx,
        );

        logger.debug({ tool: toolName, resultLen: result.length }, "Tool result");

        // Track purchase details for the final result
        if (toolName === "purchase_research") {
          const input = toolInput as {
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

        messages.push({
          role: "tool",
          tool_call_id: toolCall.id,
          content: result,
        });
      }
    }
  }

  return lastResult;
}

function formatCost(budget: BudgetTracker): string {
  return `$${budget.getStatus().dailySpent.toFixed(2)}`;
}
