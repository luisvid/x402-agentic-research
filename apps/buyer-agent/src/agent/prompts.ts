/**
 * System prompt and few-shot examples for the research buyer agent.
 */

export const SYSTEM_PROMPT = `You are a research buyer agent. Your job is to help users purchase Web3 market research reports from a paid API.

You have access to the following tools:

1. **list_tiers** — Lists available research tiers with pricing and features.
2. **check_budget** — Checks if a tier purchase is within budget limits.
3. **purchase_research** — Purchases a research report for a given query, date range, and tier.

## Workflow
1. When the user gives a research goal, first call **list_tiers** to understand options.
2. Choose the most appropriate tier based on the goal complexity. Use "basic" for simple lookups, "pro" for detailed analysis, and "deep" only for comprehensive investigations.
3. Call **check_budget** with the chosen tier to verify it's within limits.
4. Formulate a precise research query from the user's goal.
5. Call **purchase_research** with the query, a reasonable date range, and the chosen tier.
6. Summarize the results for the user, highlighting key findings.

## Guidelines
- Always check budget before purchasing.
- Prefer "pro" tier for most requests — it balances depth and cost.
- Keep research queries specific and focused (minimum 10 characters).
- Use date ranges that make sense for the topic (typically 3-6 months).
- If the purchase fails, explain the error clearly.`;

/** Anthropic-format tool definitions (kept for reference) */
export const TOOL_DEFINITIONS = [
  {
    name: "list_tiers",
    description:
      "List available research tiers with pricing, descriptions, and features.",
    input_schema: {
      type: "object" as const,
      properties: {},
      required: [] as string[],
    },
  },
  {
    name: "check_budget",
    description:
      "Check if purchasing a specific tier is within the configured budget limits. Returns whether the purchase is allowed and the current budget status.",
    input_schema: {
      type: "object" as const,
      properties: {
        tier: {
          type: "string" as const,
          enum: ["basic", "pro", "deep"],
          description: "The research tier to check budget for",
        },
      },
      required: ["tier"],
    },
  },
  {
    name: "purchase_research",
    description:
      "Purchase a research report from the paid API. Handles x402 payment automatically. Returns the research results including summary, key findings, and optionally a full report.",
    input_schema: {
      type: "object" as const,
      properties: {
        query: {
          type: "string" as const,
          description:
            "The research query (minimum 10 characters). Should be specific and focused.",
        },
        start_date: {
          type: "string" as const,
          description: "Start date in YYYY-MM-DD format",
        },
        end_date: {
          type: "string" as const,
          description: "End date in YYYY-MM-DD format",
        },
        tier: {
          type: "string" as const,
          enum: ["basic", "pro", "deep"],
          description: "Research tier to purchase",
        },
      },
      required: ["query", "start_date", "end_date", "tier"],
    },
  },
] as const;

/** OpenAI-format tool definitions (used by GEIA / OpenAI-compatible endpoints) */
export const TOOL_DEFINITIONS_OPENAI = [
  {
    type: "function" as const,
    function: {
      name: "list_tiers",
      description:
        "List available research tiers with pricing, descriptions, and features.",
      parameters: {
        type: "object" as const,
        properties: {},
        required: [] as string[],
      },
    },
  },
  {
    type: "function" as const,
    function: {
      name: "check_budget",
      description:
        "Check if purchasing a specific tier is within the configured budget limits. Returns whether the purchase is allowed and the current budget status.",
      parameters: {
        type: "object" as const,
        properties: {
          tier: {
            type: "string" as const,
            enum: ["basic", "pro", "deep"],
            description: "The research tier to check budget for",
          },
        },
        required: ["tier"],
      },
    },
  },
  {
    type: "function" as const,
    function: {
      name: "purchase_research",
      description:
        "Purchase a research report from the paid API. Handles x402 payment automatically. Returns the research results including summary, key findings, and optionally a full report.",
      parameters: {
        type: "object" as const,
        properties: {
          query: {
            type: "string" as const,
            description:
              "The research query (minimum 10 characters). Should be specific and focused.",
          },
          start_date: {
            type: "string" as const,
            description: "Start date in YYYY-MM-DD format",
          },
          end_date: {
            type: "string" as const,
            description: "End date in YYYY-MM-DD format",
          },
          tier: {
            type: "string" as const,
            enum: ["basic", "pro", "deep"],
            description: "Research tier to purchase",
          },
        },
        required: ["query", "start_date", "end_date", "tier"],
      },
    },
  },
];
