/**
 * qb-fork: pure helpers for the Invoices/Bills and Customers/Vendors pages
 * (no DOM imports, so they can be unit tested).
 */

const DAY = 24 * 60 * 60 * 1000;

/** Whole days from `from` to `to` (both UTC dates). */
export function days_between(from: Date, to: Date): number {
  return Math.round((to.getTime() - from.getTime()) / DAY);
}

/** Label for an invoice status. */
export function status_label(status: string): string {
  return (
    {
      paid: "Paid",
      open: "Open",
      partial: "Partially paid",
      overdue: "Overdue",
    }[status] ?? status
  );
}

/** Tabs on the Invoices page: [filter, label]. */
export const STATUS_TABS: readonly [string, string][] = [
  ["", "All"],
  ["unpaid", "Unpaid"],
  ["overdue", "Overdue"],
  ["paid", "Paid"],
];

/** Whether an invoice with `status` shows under the tab `tab`. */
export function in_tab(status: string, tab: string): boolean {
  if (tab === "unpaid") {
    return status !== "paid";
  }
  return tab === "" || status === tab;
}

interface Summarised {
  status: string;
  balance: number;
  amount: number;
  date: Date;
}

/**
 * Money bar totals in cents: overdue and not-yet-due balances, and invoices
 * paid that were dated in the last 30 days.
 */
export function summary(
  invoices: readonly Summarised[],
  today: Date,
): { overdue: number; not_due: number; paid_30: number } {
  const sum = { overdue: 0, not_due: 0, paid_30: 0 };
  for (const inv of invoices) {
    const cents = Math.round(inv.balance * 100);
    if (inv.status === "overdue") {
      sum.overdue += cents;
    } else if (inv.status === "paid") {
      if (days_between(inv.date, today) <= 30) {
        sum.paid_30 += Math.round(inv.amount * 100);
      }
    } else {
      sum.not_due += cents;
    }
  }
  return sum;
}

/** CSV columns the import maps: [field, label, required]. */
export function csv_fields(
  doc_title: string,
  party_title: string,
): [string, string, boolean][] {
  return [
    ["number", `${doc_title} number`, true],
    ["party", party_title, true],
    ["date", `${doc_title} date`, true],
    ["amount", "Total", true],
    ["due", "Due date", false],
    ["paid", "Amount paid", false],
    ["paid_date", "Date paid", false],
    ["status", "Status", false],
    ["email", `${party_title} email`, false],
    ["currency", "Currency", false],
  ];
}

/** "YYYY-MM-DD" plus `days` days. */
export function add_days(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) {
    return "";
  }
  return new Date(d.getTime() + days * DAY).toISOString().slice(0, 10);
}
