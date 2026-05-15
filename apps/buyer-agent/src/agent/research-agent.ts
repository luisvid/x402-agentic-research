/**
 * LLM-powered research agent — tool-calling loop that orchestrates
 * tier selection, budget checks, and research purchases.
 *
 * Two-model strategy:
 *   - Pre-purchase turns use BUYER_LLM_MODEL_FAST (tool routing — no reasoning needed)
 *   - Post-purchase turns use BUYER_LLM_MODEL (summarization — needs capable model)
 */

import OpenAI from "openai";
import type { AxiosInstance } from "axios";
import type { Config } from "../config.js";
import type { AgentResult } from "./types.js";
import { buildSystemPrompt, TOOL_DEFINITIONS_OPENAI } from "./prompts.js";
import { executeTool, type ToolContext } from "./tools.js";
import { BudgetTracker } from "../client/budget.js";
import { createLLMClient } from "./llm-factory.js";
import { logger } from "../index.js";

let wrapOpenAI: ((client: OpenAI) => OpenAI) | undefined;
try {
  const langsmith = await import("langsmith/wrappers");
  wrapOpenAI = langsmith.wrapOpenAI as (client: OpenAI) => OpenAI;
} catch {
  // langsmith not installed or LANGCHAIN_TRACING_V2 not set — tracing disabled
}

const MAX_TURNS = 10;

export async function runResearchAgent(
  goal: string,
  config: Config,
  client: AxiosInstance,
): Promise<AgentResult> {
  const rawClient = createLLMClient(config);
  const openai = wrapOpenAI ? wrapOpenAI(rawClient) : rawClient;
  const budget = new BudgetTracker(config);

  const toolCtx: ToolContext = { client, budget };

  const messages: OpenAI.ChatCompletionMessageParam[] = [
    { role: "system", content: buildSystemPrompt() },
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

    // Use fast model until a successful purchase is recorded, then switch to strong model
    const isPurchased = messages.some(
      (m) => m.role === "tool" && typeof m.content === "string" && m.content.includes('"success":true'),
    );
    const model = isPurchased ? config.BUYER_LLM_MODEL : config.BUYER_LLM_MODEL_FAST;

    const response = await openai.chat.completions.create({
      model,
      max_tokens: 4096,
      tools: TOOL_DEFINITIONS_OPENAI,
      messages,
    });

    const choice = response.choices[0];
    const message = choice.message;

    logger.debug(
      { finishReason: choice.finish_reason, hasToolCalls: !!message.tool_calls?.length, model },
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
