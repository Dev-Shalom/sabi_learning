import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { parse } from "yaml";

/* The plans, read from the one file that holds prices: config/plans.yaml.
 *
 * Read on the server at request time from the repository's config folder,
 * the same file `sabi/billing/plans.py` serves at /api/billing/plans. The page
 * reads the file directly for now so the landing page can be reviewed before
 * the billing API is merged; when it is, this becomes a `serverJSON` call and
 * nothing that renders plans changes.
 *
 * `{plan.field}` placeholders are filled from config/limits.yaml -- the file
 * the limiter actually enforces -- so "15 tutor questions a day" cannot drift
 * from the cap that stops the sixteenth. */

export type PlanFeature = { text: string; ready: boolean };
export type Plan = {
  key: string;
  name: string;
  summary: string;
  monthly: number;
  yearly: number | null;
  /** Whole naira saved by paying yearly, computed, never typed. */
  yearlySaving: number | null;
  features: PlanFeature[];
};
export type Plans = { checkoutOpen: boolean; plans: Plan[] };

const CONFIG = path.resolve(process.cwd(), "..", "config");

type RawPlans = {
  checkout?: { enabled?: boolean };
  plans: {
    key: string;
    name: string;
    summary: string;
    monthly_ngn: number;
    yearly_ngn?: number;
    features: { text: string; ready: boolean }[];
  }[];
};
type RawLimits = { plans: Record<string, Record<string, number | string>> };

export async function loadPlans(): Promise<Plans | null> {
  try {
    const [plansText, limitsText] = await Promise.all([
      readFile(path.join(CONFIG, "plans.yaml"), "utf8"),
      readFile(path.join(CONFIG, "limits.yaml"), "utf8"),
    ]);
    const raw = parse(plansText) as RawPlans;
    const limits = (parse(limitsText) as RawLimits).plans;

    const fill = (text: string) =>
      text.replace(/\{(\w+)\.(\w+)\}/g, (whole, plan: string, field: string) => {
        const value = limits[plan]?.[field];
        // An unknown placeholder is shown as-is rather than guessed: a visibly
        // broken line is found in review, a plausible wrong number is not.
        return value === undefined ? whole : String(value);
      });

    return {
      // Payments open only when BOTH switches are on; the key lives in the
      // API's environment, so from here the config switch is the one we know.
      checkoutOpen: raw.checkout?.enabled === true,
      plans: raw.plans.map((p) => ({
        key: p.key,
        name: p.name,
        summary: p.summary,
        monthly: p.monthly_ngn,
        yearly: p.yearly_ngn ?? null,
        yearlySaving:
          p.yearly_ngn != null ? p.monthly_ngn * 12 - p.yearly_ngn : null,
        features: p.features.map((f) => ({ text: fill(f.text), ready: f.ready })),
      })),
    };
  } catch {
    return null;
  }
}

/** ₦1,200 -- grouped the Nigerian way, no kobo. */
export function naira(n: number): string {
  return `₦${n.toLocaleString("en-NG")}`;
}
