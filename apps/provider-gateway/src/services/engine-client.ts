import axios, { AxiosInstance, AxiosError } from "axios";
import type { Config } from "../config.js";
import type { Tier } from "../schemas/research.js";
import { logger } from "../index.js";

export interface EngineRequest {
  request_id: string;
  query: string;
  start_date: string;
  end_date: string;
  tier: Tier;
  format: string;
}

export interface EngineResponse {
  request_id: string;
  status: "completed" | "failed" | "no_data";
  tier: string;
  summary: string | null;
  key_findings: Record<string, unknown>[] | null;
  causal_chain: Record<string, unknown> | null;
  sources: Record<string, unknown>[];
  confidence: number | null;
  report_markdown: string | null;
  timings: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

export function createEngineClient(config: Config): AxiosInstance {
  const client = axios.create({
    baseURL: config.RESEARCH_ENGINE_URL,
    timeout: 600_000, // 10 minutes for long-running research
    headers: { "Content-Type": "application/json" },
  });

  client.interceptors.request.use((req) => {
    logger.debug({ url: req.url }, "Engine request");
    return req;
  });

  return client;
}

export async function runResearch(
  client: AxiosInstance,
  params: EngineRequest,
): Promise<EngineResponse> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const { data } = await client.post<EngineResponse>(
        "/internal/run-research",
        params,
      );
      return data;
    } catch (err: unknown) {
      lastError = err instanceof Error ? err : new Error(String(err));
      const axiosErr = err as AxiosError;
      const status = axiosErr.response?.status;

      // Don't retry 4xx errors (client mistakes)
      if (status && status >= 400 && status < 500) {
        throw lastError;
      }

      // Retry on 5xx or network errors
      if (attempt < MAX_RETRIES - 1) {
        const delay = BASE_DELAY_MS * Math.pow(2, attempt);
        logger.warn(
          { requestId: params.request_id, attempt: attempt + 1, delay, error: lastError.message },
          "Engine call failed, retrying",
        );
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError ?? new Error("Engine request failed after retries");
}
