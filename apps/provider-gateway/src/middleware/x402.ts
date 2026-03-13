/**
 * x402 Payment Middleware Configuration.
 *
 * Protects research endpoints with per-tier pricing:
 *   POST /research/basic → $0.01 USDC
 *   POST /research/pro   → $0.03 USDC
 *   POST /research/deep  → $0.05 USDC
 *
 * Engine is ONLY called after payment validation succeeds
 * (middleware runs before route handler).
 */

import type { Express } from "express";
import { paymentMiddlewareFromConfig } from "@x402/express";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import type { Config } from "../config.js";
import { logger } from "../index.js";

// Network: Base Sepolia testnet (CAIP-2 format)
const BASE_SEPOLIA = "eip155:84532" as const;

export function setupPaymentMiddleware(app: Express, config: Config): void {
  // Skip payment middleware in mock mode
  if (config.MOCK_MODE) {
    logger.info("Mock mode: x402 payment middleware DISABLED");
    return;
  }

  const payTo = config.PROVIDER_EVM_ADDRESS;

  const routes = {
    "POST /research/basic": {
      accepts: {
        scheme: "exact",
        network: BASE_SEPOLIA,
        payTo,
        price: 0.01,
      },
    },
    "POST /research/pro": {
      accepts: {
        scheme: "exact",
        network: BASE_SEPOLIA,
        payTo,
        price: 0.03,
      },
    },
    "POST /research/deep": {
      accepts: {
        scheme: "exact",
        network: BASE_SEPOLIA,
        payTo,
        price: 0.05,
      },
    },
  };

  const facilitator = new HTTPFacilitatorClient({
    url: config.X402_FACILITATOR_URL,
  });

  const evmScheme = new ExactEvmScheme();

  const middleware = paymentMiddlewareFromConfig(
    routes,
    facilitator,
    [{ network: BASE_SEPOLIA, server: evmScheme }],
  );

  app.use(middleware);

  logger.info("x402 payment middleware ENABLED");
  logger.info(`  basic: $0.01 USDC → ${payTo}`);
  logger.info(`  pro:   $0.03 USDC → ${payTo}`);
  logger.info(`  deep:  $0.05 USDC → ${payTo}`);
}
