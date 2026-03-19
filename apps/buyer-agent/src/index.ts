import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, "../../../.env") });

import { Command } from "commander";
import pino from "pino";
import { loadConfig } from "./config.js";
import { createX402Client, purchaseResearch } from "./client/x402-client.js";
import { BudgetTracker } from "./client/budget.js";
import { runResearchAgent } from "./agent/research-agent.js";
import { displayResult, displayDirectResult } from "./display.js";

const config = loadConfig();

export const logger = pino({
  level: config.LOG_LEVEL,
  transport:
    process.env.NODE_ENV !== "production"
      ? { target: "pino-pretty" }
      : undefined,
});

const program = new Command();

program
  .name("buyer")
  .description("AI buyer agent for x402 research purchases")
  .version("0.1.0");

program
  .command("agent")
  .description("Run the LLM-powered research agent")
  .argument("<goal>", "Research goal in natural language")
  .action(async (goal: string) => {
    logger.info({ goal }, "Starting research agent");

    const client = createX402Client(config);
    const result = await runResearchAgent(goal, config, client);

    displayResult(result);

    if (!result.success) {
      process.exitCode = 1;
    }
  });

program
  .command("direct")
  .description("Directly purchase research (bypass agent)")
  .requiredOption("--query <query>", "Research query")
  .requiredOption("--start-date <date>", "Start date (YYYY-MM-DD)")
  .requiredOption("--end-date <date>", "End date (YYYY-MM-DD)")
  .option("--tier <tier>", "Research tier", "pro")
  .action(
    async (opts: {
      query: string;
      startDate: string;
      endDate: string;
      tier: string;
    }) => {
      logger.info({ ...opts }, "Direct research purchase");

      const budget = new BudgetTracker(config);
      const check = budget.checkBudget(opts.tier);
      if (!check.allowed) {
        logger.error({ reason: check.reason }, "Budget check failed");
        console.error(`Budget check failed: ${check.reason}`);
        process.exitCode = 1;
        return;
      }

      const client = createX402Client(config);

      try {
        const result = await purchaseResearch(client, opts.tier, {
          query: opts.query,
          start_date: opts.startDate,
          end_date: opts.endDate,
        });

        budget.recordSpend(opts.tier);
        const price = BudgetTracker.getTierPrice(opts.tier) ?? 0;

        displayDirectResult(
          opts.tier,
          `$${price.toFixed(2)}`,
          result as unknown as Record<string, unknown>,
        );
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Unknown error";
        logger.error({ err }, "Direct purchase failed");
        console.error(`Purchase failed: ${message}`);
        process.exitCode = 1;
      }
    },
  );

program.parse();
