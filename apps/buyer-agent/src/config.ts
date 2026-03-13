import { z } from "zod";

const envSchema = z.object({
  GATEWAY_URL: z.string().default("http://localhost:8200"),
  BUYER_EVM_PRIVATE_KEY: z.string().default("0x0000000000000000000000000000000000000000000000000000000000000001"),
  AGENT_LLM_API_KEY: z.string().default(""),
  AGENT_LLM_MODEL: z.string().default("claude-sonnet-4-20250514"),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
  MOCK_MODE: z
    .string()
    .transform((v) => v === "true")
    .default("false"),
  DAILY_BUDGET_USD: z.coerce.number().default(1.0),
  PER_REQUEST_LIMIT_USD: z.coerce.number().default(0.10),
});

export type Config = z.infer<typeof envSchema>;

export function loadConfig(): Config {
  return envSchema.parse(process.env);
}
