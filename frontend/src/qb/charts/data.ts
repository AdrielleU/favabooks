/**
 * qb-fork: chart data from report results (no DOM imports, so it can be
 * unit tested).
 */
import type { QbNode, QbStatement } from "../api.ts";

export interface TrendPoint {
  label: string;
  start: Date | null;
  end: Date;
  income: number;
  expenses: number;
  net: number;
}

const block = (statement: QbStatement, key: string) =>
  statement.blocks.find((b) => b.key === key);

/** Income, expenses (incl. cost of goods) and net per column, no Total. */
export function pnl_trend(statement: QbStatement): TrendPoint[] {
  const income = block(statement, "income")?.amounts ?? [];
  const cogs = block(statement, "cogs")?.amounts ?? [];
  const expenses = block(statement, "expenses")?.amounts ?? [];
  const net = block(statement, "net")?.amounts ?? [];
  return statement.columns.flatMap((column, i) =>
    column.label === "Total" && statement.columns.length > 1
      ? []
      : [
          {
            label: column.label,
            start: column.start,
            end: column.end,
            income: income[i] ?? 0,
            expenses: (expenses[i] ?? 0) + (cogs[i] ?? 0),
            net: net[i] ?? 0,
          },
        ],
  );
}

export interface Slice {
  label: string;
  account: string;
  value: number;
}

/**
 * The biggest categories of a section's total column (first level under
 * the root), the rest as "Other". Negative amounts (refunds) are left out.
 */
export function top_slices(
  node: QbNode | null,
  column: number,
  count = 6,
): Slice[] {
  if (!node) {
    return [];
  }
  const slices = node.children
    .map((child) => ({
      label: child.name,
      account: child.account,
      value: child.amounts[column] ?? 0,
    }))
    .filter((s) => s.value > 0)
    .sort((a, b) => b.value - a.value);
  if (slices.length <= count) {
    return slices;
  }
  const rest = slices.slice(count - 1);
  return [
    ...slices.slice(0, count - 1),
    {
      label: `Other (${rest.length.toString()})`,
      account: "",
      value: rest.reduce((sum, s) => sum + s.value, 0),
    },
  ];
}

/** Breakdown that keeps a chart readable: months up to 2 years, then
 * quarters up to 6 years, then years. */
export function trend_by(start: Date, end: Date): "month" | "quarter" | "year" {
  const months =
    (end.getUTCFullYear() - start.getUTCFullYear()) * 12 +
    end.getUTCMonth() -
    start.getUTCMonth() +
    1;
  return months <= 24 ? "month" : months <= 72 ? "quarter" : "year";
}

/** The headline figures for a P&L total column (and the previous one). */
export function kpis(
  statement: QbStatement,
  column: number,
): { income: number; expenses: number; net: number; margin: number | null } {
  const at = (key: string) => block(statement, key)?.amounts[column] ?? 0;
  const income = at("income");
  const expenses = at("expenses") + at("cogs");
  const net = at("net");
  return {
    income,
    expenses,
    net,
    margin: income === 0 ? null : (net / income) * 100,
  };
}

/** "+12.5% vs previous period" style text, or "" without a base. */
export function change_text(
  current: number,
  previous: number,
  suffix: string,
): string {
  if (previous === 0) {
    return "";
  }
  const pct = ((current - previous) / Math.abs(previous)) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}% ${suffix}`;
}
