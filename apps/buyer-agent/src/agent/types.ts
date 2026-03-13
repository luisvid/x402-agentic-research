export interface AgentResult {
  goal: string;
  tier: string;
  query: string;
  startDate: string;
  endDate: string;
  summary: string | null;
  keyFindings: Record<string, unknown>[] | null;
  cost: string;
  success: boolean;
  error?: string;
}

export interface TierInfo {
  name: string;
  price: string;
  description: string;
  features: string[];
}

export const TIERS: TierInfo[] = [
  {
    name: "basic",
    price: "$0.01",
    description: "Quick lookup with key findings only",
    features: ["Up to 8 search queries", "Key findings summary", "No full report", "No causal chain"],
  },
  {
    name: "pro",
    price: "$0.03",
    description: "Detailed analysis with full report and causal chain",
    features: ["Up to 15 search queries", "Full markdown report", "Causal chain analysis", "Multi-step LLM reasoning"],
  },
  {
    name: "deep",
    price: "$0.05",
    description: "Comprehensive research with maximum coverage",
    features: ["Up to 25 search queries", "Full markdown report", "Causal chain analysis", "Maximum article coverage"],
  },
];
