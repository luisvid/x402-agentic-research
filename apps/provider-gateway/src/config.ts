import { z } from "zod";

const envSchema = z.object({
  PORT: z.coerce.number().default(8200),
  RESEARCH_ENGINE_URL: z.string().default("http://localhost:8100"),
  X402_FACILITATOR_URL: z
    .string()
    .default("https://x402.org/facilitator"),
  PROVIDER_EVM_ADDRESS: z.string().default("0x0000000000000000000000000000000000000000"),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
  MOCK_MODE: z
    .string()
    .transform((v) => v === "true")
    .default("false"),
});

export type Config = z.infer<typeof envSchema>;

export function loadConfig(): Config {
  return envSchema.parse(process.env);
}
