import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, "../../../.env") });

import express from "express";
import { mkdirSync } from "fs";
import pino from "pino";
import { loadConfig } from "./config.js";
import { researchRouter } from "./routes/research.js";
import { adminRouter } from "./routes/admin.js";
import { requestIdMiddleware } from "./middleware/request-id.js";
import { errorHandler } from "./middleware/error-handler.js";
import { setupPaymentMiddleware } from "./middleware/x402.js";
import { AuditStore } from "./services/audit-store.js";

const config = loadConfig();

export const logger = pino({
  level: config.LOG_LEVEL,
  transport:
    process.env.NODE_ENV !== "production"
      ? { target: "pino-pretty" }
      : undefined,
});

// Ensure data directory exists for SQLite
mkdirSync("data", { recursive: true });
const auditStore = new AuditStore("data/audit.db");

const app: ReturnType<typeof express> = express();

app.use(express.json());
app.use(requestIdMiddleware);

app.get("/health", async (_req, res) => {
  let engineStatus = "unknown";
  try {
    const resp = await fetch(`${config.RESEARCH_ENGINE_URL}/health`);
    engineStatus = resp.ok ? "ok" : "degraded";
  } catch {
    engineStatus = "unreachable";
  }
  res.json({
    status: "ok",
    service: "provider-gateway",
    engine: engineStatus,
    mock_mode: config.MOCK_MODE,
  });
});

// x402 payment middleware — protects /research/:tier routes
// Must be applied BEFORE the research router so payment validates first
setupPaymentMiddleware(app, config);

app.use("/research", researchRouter(config, auditStore));
app.use("/admin", adminRouter(auditStore));

app.use(errorHandler);

const port = config.PORT;
app.listen(port, () => {
  logger.info(`Provider gateway listening on port ${port}`);
  logger.info(`Engine URL: ${config.RESEARCH_ENGINE_URL}`);
  logger.info(`Pay-to address: ${config.PROVIDER_EVM_ADDRESS}`);
  logger.info(`Mock mode: ${config.MOCK_MODE}`);
});

export { app, config };
