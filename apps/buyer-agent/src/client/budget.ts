/**
 * Budget tracking — enforces per-request and daily spending limits.
 */

import type { Config } from "../config.js";
import { logger } from "../index.js";

const TIER_PRICES: Record<string, number> = {
  basic: 0.01,
  pro: 0.03,
  deep: 0.05,
};

export class BudgetTracker {
  private dailySpent = 0;
  private readonly dailyLimit: number;
  private readonly perRequestLimit: number;

  constructor(config: Config) {
    this.dailyLimit = config.DAILY_BUDGET_USD;
    this.perRequestLimit = config.PER_REQUEST_LIMIT_USD;
  }

  checkBudget(tier: string): { allowed: boolean; reason?: string } {
    const price = TIER_PRICES[tier];
    if (price === undefined) {
      return { allowed: false, reason: `Unknown tier: ${tier}` };
    }

    if (price > this.perRequestLimit) {
      return {
        allowed: false,
        reason: `Tier "${tier}" costs $${price} which exceeds per-request limit of $${this.perRequestLimit}`,
      };
    }

    if (this.dailySpent + price > this.dailyLimit) {
      return {
        allowed: false,
        reason: `Daily budget exhausted: spent $${this.dailySpent.toFixed(2)} of $${this.dailyLimit} limit`,
      };
    }

    return { allowed: true };
  }

  recordSpend(tier: string): void {
    const price = TIER_PRICES[tier] ?? 0;
    this.dailySpent += price;
    logger.info(
      { tier, price, dailySpent: this.dailySpent, dailyLimit: this.dailyLimit },
      "Spend recorded",
    );
  }

  getStatus(): { dailySpent: number; dailyLimit: number; remaining: number } {
    return {
      dailySpent: this.dailySpent,
      dailyLimit: this.dailyLimit,
      remaining: this.dailyLimit - this.dailySpent,
    };
  }

  static getTierPrice(tier: string): number | undefined {
    return TIER_PRICES[tier];
  }
}
