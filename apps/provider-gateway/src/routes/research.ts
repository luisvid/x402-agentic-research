import { Router, Request, Response } from "express";
import { v4 as uuidv4 } from "uuid";
import type { Config } from "../config.js";
import {
  researchRequestSchema,
  tierSchema,
  TIER_PRICES,
  type Tier,
} from "../schemas/research.js";
import {
  createEngineClient,
  runResearch,
  type EngineRequest,
} from "../services/engine-client.js";
import type { AuditStore } from "../services/audit-store.js";
import { logger } from "../index.js";

export function researchRouter(config: Config, audit?: AuditStore): Router {
  const router = Router();
  const engineClient = createEngineClient(config);

  const handleResearch = async (
    req: Request,
    res: Response,
    tier: Tier,
  ): Promise<void> => {
    const requestId =
      (req.headers["x-request-id"] as string) || uuidv4();
    const startTime = Date.now();

    // Validate request body
    const parsed = researchRequestSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({
        error: "Invalid request",
        details: parsed.error.flatten().fieldErrors,
        request_id: requestId,
      });
      return;
    }

    const engineReq: EngineRequest = {
      request_id: requestId,
      query: parsed.data.query,
      start_date: parsed.data.start_date,
      end_date: parsed.data.end_date,
      tier,
      format: parsed.data.format,
    };

    logger.info(
      { requestId, tier, query: engineReq.query },
      "Research request received",
    );

    // Record the request in audit store
    if (audit) {
      audit.insert({
        request_id: requestId,
        query: parsed.data.query,
        tier,
        quoted_price: TIER_PRICES[tier],
        asset: "USDC",
        network: "base-sepolia",
        payment_status: config.MOCK_MODE ? "mock" : "paid",
        provider_status: "pending",
        engine_latency_ms: null,
        created_at: new Date().toISOString(),
      });
    }

    try {
      const result = await runResearch(engineClient, engineReq);
      const latencyMs = Date.now() - startTime;

      // Update audit record
      if (audit) {
        audit.complete(requestId, result.status, latencyMs);
      }

      logger.info(
        { requestId, tier, status: result.status, latencyMs },
        "Research completed",
      );

      res.json(result);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Engine request failed";
      const latencyMs = Date.now() - startTime;

      if (audit) {
        audit.complete(requestId, "failed", latencyMs);
      }

      logger.error({ requestId, err, latencyMs }, "Engine call failed");
      res.status(502).json({
        error: "Research engine error",
        message: msg,
        request_id: requestId,
      });
    }
  };

  router.post("/:tier", async (req: Request, res: Response) => {
    const tierResult = tierSchema.safeParse(req.params.tier);
    if (!tierResult.success) {
      res.status(400).json({
        error: `Invalid tier: ${req.params.tier}. Must be basic, pro, or deep`,
      });
      return;
    }
    await handleResearch(req, res, tierResult.data);
  });

  return router;
}
