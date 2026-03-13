import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Express, Request, Response, NextFunction } from "express";

// Mock @x402/express before any imports
vi.mock("@x402/express", () => ({
  paymentMiddlewareFromConfig: vi.fn(
    () => (_req: Request, _res: Response, next: NextFunction) => next(),
  ),
}));

vi.mock("@x402/core/server", () => ({
  HTTPFacilitatorClient: vi.fn().mockImplementation(() => ({})),
}));

vi.mock("@x402/evm/exact/server", () => ({
  ExactEvmScheme: vi.fn().mockImplementation(() => ({ scheme: "exact" })),
}));

// Mock logger to avoid circular import from index.ts
vi.mock("../index.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { setupPaymentMiddleware } from "../middleware/x402.js";
import { paymentMiddlewareFromConfig } from "@x402/express";

function createMockApp(): Express {
  const handlers: Array<(...args: unknown[]) => void> = [];
  return {
    use: vi.fn((handler: (...args: unknown[]) => void) => handlers.push(handler)),
  } as unknown as Express;
}

function createMockConfig(overrides: Record<string, unknown> = {}) {
  return {
    PORT: 8200,
    RESEARCH_ENGINE_URL: "http://localhost:8100",
    X402_FACILITATOR_URL: "https://x402.org/facilitator",
    PROVIDER_EVM_ADDRESS: "0xTestAddress",
    LOG_LEVEL: "info" as const,
    MOCK_MODE: false,
    ...overrides,
  };
}

describe("x402 payment middleware", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("skips middleware in mock mode", () => {
    const app = createMockApp();
    const config = createMockConfig({ MOCK_MODE: true });

    setupPaymentMiddleware(app, config);

    expect(app.use).not.toHaveBeenCalled();
    expect(paymentMiddlewareFromConfig).not.toHaveBeenCalled();
  });

  it("registers middleware when not in mock mode", () => {
    const app = createMockApp();
    const config = createMockConfig();

    setupPaymentMiddleware(app, config);

    expect(paymentMiddlewareFromConfig).toHaveBeenCalledOnce();
    expect(app.use).toHaveBeenCalledOnce();
  });

  it("configures correct routes with tier pricing", () => {
    const app = createMockApp();
    const config = createMockConfig({
      PROVIDER_EVM_ADDRESS: "0xMyAddr",
    });

    setupPaymentMiddleware(app, config);

    const routesArg = vi.mocked(paymentMiddlewareFromConfig).mock.calls[0][0];
    expect(routesArg).toHaveProperty("POST /research/basic");
    expect(routesArg).toHaveProperty("POST /research/pro");
    expect(routesArg).toHaveProperty("POST /research/deep");

    const basicRoute = (routesArg as Record<string, unknown>)["POST /research/basic"] as {
      accepts: { price: number; payTo: string; network: string };
    };
    expect(basicRoute.accepts.price).toBe(0.01);
    expect(basicRoute.accepts.payTo).toBe("0xMyAddr");
    expect(basicRoute.accepts.network).toBe("eip155:84532");
  });

  it("passes facilitator and scheme registration", () => {
    const app = createMockApp();
    const config = createMockConfig();

    setupPaymentMiddleware(app, config);

    const args = vi.mocked(paymentMiddlewareFromConfig).mock.calls[0];
    // args[1] = facilitator, args[2] = scheme registrations
    expect(args[1]).toBeDefined();
    expect(args[2]).toHaveLength(1);
    expect(args[2]![0]).toHaveProperty("network", "eip155:84532");
    expect(args[2]![0]).toHaveProperty("server");
  });
});
