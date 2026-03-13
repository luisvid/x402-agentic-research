/**
 * x402 payment client — wraps axios with automatic 402 → pay → retry.
 *
 * When a request returns 402 Payment Required, the x402 interceptor
 * parses payment requirements, signs with the buyer's private key,
 * and retries the request with a payment header.
 */

import axios, { type AxiosInstance } from "axios";
import { wrapAxiosWithPayment, x402Client } from "@x402/axios";
import { registerExactEvmScheme } from "@x402/evm/exact/client";
import { toClientEvmSigner } from "@x402/evm";
import { privateKeyToAccount } from "viem/accounts";
import { createPublicClient, http } from "viem";
import { baseSepolia } from "viem/chains";
import type { Config } from "../config.js";
import { logger } from "../index.js";

export interface ResearchRequest {
  query: string;
  start_date: string;
  end_date: string;
  format?: string;
}

export interface ResearchResponse {
  request_id: string;
  status: "completed" | "failed" | "no_data";
  tier: string;
  summary: string | null;
  key_findings: Record<string, unknown>[] | null;
  causal_chain: Record<string, unknown> | null;
  sources: Record<string, unknown>[] | null;
  confidence: number | null;
  report_markdown: string | null;
  timings: Record<string, number> | null;
  metadata: Record<string, unknown> | null;
}

export function createX402Client(config: Config): AxiosInstance {
  const account = privateKeyToAccount(
    config.BUYER_EVM_PRIVATE_KEY as `0x${string}`,
  );

  const publicClient = createPublicClient({
    chain: baseSepolia,
    transport: http(),
  });

  const signer = toClientEvmSigner(account, publicClient);

  const client = new x402Client();
  registerExactEvmScheme(client, { signer });

  const axiosInstance = axios.create({
    baseURL: config.GATEWAY_URL,
    timeout: 660_000, // 11 min — slightly longer than engine timeout
  });

  const wrapped = wrapAxiosWithPayment(axiosInstance, client);

  logger.info(
    { address: account.address, gateway: config.GATEWAY_URL },
    "x402 client initialized",
  );

  return wrapped;
}

export async function purchaseResearch(
  client: AxiosInstance,
  tier: string,
  request: ResearchRequest,
): Promise<ResearchResponse> {
  logger.info({ tier, query: request.query }, "Sending research request");

  const response = await client.post<ResearchResponse>(
    `/research/${tier}`,
    request,
  );

  logger.info(
    { tier, status: response.data.status, requestId: response.data.request_id },
    "Research response received",
  );

  return response.data;
}
