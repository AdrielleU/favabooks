/**
 * qb-fork: pure helpers for the All transactions and Bulk reclassify pages
 * (no DOM imports, so they can be unit tested).
 */

/** "Expenses:Office:Supplies" -> "Office:Supplies" (the root alone stays). */
export function leaf(account: string): string {
  const i = account.indexOf(":");
  return i === -1 ? account : account.slice(i + 1);
}

/** Tabs on the All transactions page: [kind, label]. */
export const KIND_TABS: readonly [string, string][] = [
  ["", "All"],
  ["expense", "Expenses"],
  ["income", "Income"],
  ["transfer", "Transfers"],
  ["other", "Other"],
  ["review", "Needs review"],
];

/** Badge label for a transaction's kind. */
export function kind_label(kind: string): string {
  return (
    { expense: "Expense", income: "Income", transfer: "Transfer" }[kind] ??
    "Journal"
  );
}

/** Sum of amounts per kind, in cents, for the summary line. */
export function totals(
  rows: readonly { kind: string; amount: number }[],
): Record<"expense" | "income", number> {
  const sum = { expense: 0, income: 0 };
  for (const row of rows) {
    if (row.kind === "expense" || row.kind === "income") {
      sum[row.kind] += Math.round(row.amount * 100);
    }
  }
  return sum;
}
