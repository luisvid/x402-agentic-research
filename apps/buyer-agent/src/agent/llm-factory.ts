/**
 * LLM client factory — creates a provider-configured OpenAI-compatible client.
 *
 * Supported providers:
 *   openai    — uses OPENAI_API_KEY with the native OpenAI API
 *   anthropic — not yet supported in TypeScript; requires @anthropic-ai/sdk
 *               and a rewrite of the tool-calling loop (different API shape).
 *               Use the Python research engine for Anthropic support.
 *
 * Adding a new provider: implement the client creation here and register
 * it in the switch below. The buyer agent loop (research-agent.ts) uses
 * OpenAI's chat.completions.create() shape — a new provider must be
 * OpenAI-compatible or the loop must be abstracted further.
 */

import OpenAI from "openai";
import type { Config } from "../config.js";

export function createLLMClient(config: Config): OpenAI {
  switch (config.LLM_PROVIDER) {
    case "openai":
      return new OpenAI({ apiKey: config.OPENAI_API_KEY });

    case "anthropic":
      throw new Error(
        "Anthropic provider is not yet supported in the TypeScript buyer agent. " +
        "Set LLM_PROVIDER=openai or use the Python research engine for Anthropic models."
      );

    default:
      throw new Error(`Unknown LLM_PROVIDER: ${config.LLM_PROVIDER}`);
  }
}
