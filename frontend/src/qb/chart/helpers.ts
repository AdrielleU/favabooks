/**
 * qb-fork: pure helpers for the Chart of accounts (no DOM imports, so they
 * can be unit tested).
 */
/**
 * A name as a Beancount account component: words joined in CamelCase
 * ("office supplies" -> "OfficeSupplies"); "X" in front if it doesn't
 * start with a letter or digit.
 */
export function component(name: string): string {
  const joined = name
    .replace(/[^A-Za-z0-9 -]+/g, "")
    .split(/[\s]+/)
    .filter(Boolean)
    .map((w) => (w[0] ?? "").toUpperCase() + w.slice(1))
    .join("");
  return joined === "" || /^[A-Z0-9]/.test(joined) ? joined : `X${joined}`;
}

/** QuickBooks account types in the order QuickBooks lists them. */
export const TYPE_ORDER = [
  "Bank",
  "Accounts receivable (A/R)",
  "Other Current Assets",
  "Fixed Assets",
  "Accounts payable (A/P)",
  "Credit Card",
  "Other Current Liabilities",
  "Long Term Liabilities",
  "Equity",
  "Income",
  "Other Income",
  "Cost of Goods Sold",
  "Expenses",
];

/** Sort key for an account type (unknown types last). */
export function type_rank(type: string): number {
  const i = TYPE_ORDER.indexOf(type);
  return i === -1 ? TYPE_ORDER.length : i;
}

/** Kinds of new account: [key, label, root kind, parent path under root]. */
export const NEW_KINDS: readonly [string, string, string, string][] = [
  ["bank", "Bank account (checking, savings)", "assets", "Bank"],
  ["card", "Credit card", "liabilities", "CreditCard"],
  ["expense", "Expense category", "expenses", ""],
  ["income", "Income category", "income", ""],
  ["cogs", "Cost of goods sold", "expenses", "COGS"],
  ["asset", "Other asset (equipment, deposits)", "assets", ""],
  ["receivable", "Accounts receivable", "assets", ""],
  ["payable", "Accounts payable", "liabilities", ""],
  ["liability", "Loan or other liability", "liabilities", ""],
  ["equity", "Equity (owner contributions, draws)", "equity", ""],
];

/**
 * The Beancount account for a new account: root, the kind's parent, an
 * optional parent account, and the name made into an account component.
 */
export function new_account_name(
  root: string,
  kind_parent: string,
  parent: string,
  name: string,
): string {
  const leaf = component(name);
  const base = parent || [root, kind_parent].filter(Boolean).join(":");
  return leaf ? `${base}:${leaf}` : base;
}

/** "Expenses:Legal:Startup" -> ["Legal", "Startup"] (no root). */
export function path_parts(account: string): string[] {
  return account.split(":").slice(1);
}
