import { z } from "zod";

const MAX_DATE_RANGE_DAYS = 365;

export const researchRequestSchema = z
  .object({
    query: z.string().min(10, "Query must be at least 10 characters").max(500, "Query too long"),
    start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Must be YYYY-MM-DD"),
    end_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Must be YYYY-MM-DD"),
    format: z.enum(["json", "markdown", "both"]).default("both"),
  })
  .refine(
    (data) => {
      const start = new Date(data.start_date);
      const end = new Date(data.end_date);
      return end > start;
    },
    { message: "end_date must be after start_date", path: ["end_date"] },
  )
  .refine(
    (data) => {
      const start = new Date(data.start_date);
      const end = new Date(data.end_date);
      const diffDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);
      return diffDays <= MAX_DATE_RANGE_DAYS;
    },
    { message: `Date range must not exceed ${MAX_DATE_RANGE_DAYS} days`, path: ["end_date"] },
  );

export const tierSchema = z.enum(["basic", "pro", "deep"]);

export type ResearchRequest = z.infer<typeof researchRequestSchema>;
export type Tier = z.infer<typeof tierSchema>;

export const TIER_PRICES: Record<Tier, string> = {
  basic: "$0.01",
  pro: "$0.03",
  deep: "$0.05",
};
