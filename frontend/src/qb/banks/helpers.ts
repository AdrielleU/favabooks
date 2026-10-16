/**
 * qb-fork: pure helpers for the Bank & card accounts page (no DOM imports,
 * so they can be unit tested).
 */
import type { QbLayout } from "../api.ts";

/** What a statement column is used as, in the column-mapping step. */
export type Role =
  | "date"
  | "description"
  | "amount"
  | "debit"
  | "credit"
  | "balance"
  | "ignore";

export const ROLES: readonly [Role, string][] = [
  ["ignore", "Ignore"],
  ["date", "Date"],
  ["description", "Description / payee"],
  ["amount", "Amount"],
  ["debit", "Money out"],
  ["credit", "Money in"],
  ["balance", "Balance"],
];

/** Date formats offered for custom files ("" tries common ones). */
export const DATE_FORMATS: readonly [string, string][] = [
  ["", "Detect automatically"],
  ["%m/%d/%Y", "MM/DD/YYYY"],
  ["%m/%d/%y", "MM/DD/YY"],
  ["%d/%m/%Y", "DD/MM/YYYY"],
  ["%Y-%m-%d", "YYYY-MM-DD"],
  ["%m-%d-%Y", "MM-DD-YYYY"],
  ["%d.%m.%Y", "DD.MM.YYYY"],
];

/** "Bank of America" -> "BankOfAmerica" (an account-name component). */
export function account_component(name: string): string {
  const joined = name
    .replace(/[^A-Za-z0-9 ]+/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => (w[0] ?? "").toUpperCase() + w.slice(1))
    .join("");
  return /^[A-Z]/.test(joined) ? joined : `Bank${joined}`;
}

/** A ledger account to suggest for a new connection. */
export function suggest_account(
  bank: string,
  kind: string,
  last4: string,
): string {
  if (bank === "Stripe") {
    return "Assets:Stripe";
  }
  const root = /card/i.test(kind) ? "Liabilities:CreditCard" : "Assets:Bank";
  const digits = last4.replace(/\D/g, "");
  return `${root}:${account_component(bank)}${digits ? `-${digits}` : ""}`;
}

/** A first guess at a column's role from its header text. */
export function guess_role(header: string): Role {
  const h = header.toLowerCase();
  if (h.includes("balance")) {
    return "balance";
  }
  if (/date|posted/.test(h)) {
    return "date";
  }
  if (/debit|withdraw|money out|^out$|outflow|charge/.test(h)) {
    return "debit";
  }
  if (/credit|deposit|money in|^in$|inflow/.test(h)) {
    return "credit";
  }
  if (h.includes("amount")) {
    return "amount";
  }
  if (/desc|payee|name|merchant|memo|narration|details/.test(h)) {
    return "description";
  }
  return "ignore";
}

const DATE_VALUE = /^\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}/;
const NUMBER_VALUE = /^[($-]*\d[\d,]*(\.\d+)?\)?$/;

/**
 * Guessed roles for a header row; each role is used once at most. When the
 * header names give no clue, sample values do: a column of dates is the
 * Date, the first text column the Description.
 */
export function guess_roles(
  header: readonly string[],
  sample: readonly (readonly string[])[] = [],
): Role[] {
  const used = new Set<Role>();
  const roles = header.map((column): Role => {
    const role = guess_role(column);
    if (role === "ignore" || used.has(role)) {
      return "ignore";
    }
    used.add(role);
    return role;
  });
  const values = (i: number) =>
    sample.map((row) => (row[i] ?? "").trim()).filter((v) => v !== "");
  const all = (i: number, test: RegExp) => {
    const v = values(i);
    return v.length > 0 && v.every((value) => test.test(value));
  };
  for (const role of ["date", "description"] as const) {
    if (used.has(role)) {
      continue;
    }
    const index = roles.findIndex(
      (r, i) =>
        r === "ignore" &&
        (role === "date"
          ? all(i, DATE_VALUE)
          : values(i).length > 0 &&
            !all(i, NUMBER_VALUE) &&
            !all(i, DATE_VALUE)),
    );
    if (index >= 0) {
      roles[index] = role;
      used.add(role);
    }
  }
  return roles;
}

/** Why roles can't be saved yet ("" when they can). */
export function roles_problem(roles: readonly Role[]): string {
  const count = (role: Role) => roles.filter((r) => r === role).length;
  for (const [role, label] of ROLES) {
    if (role !== "ignore" && count(role) > 1) {
      return `Two columns are set to ${label}.`;
    }
  }
  if (!count("date")) {
    return "Choose a Date column.";
  }
  if (!count("description")) {
    return "Choose a Description column.";
  }
  if (!count("amount") && !(count("debit") && count("credit"))) {
    return "Choose an Amount column, or both Money out and Money in.";
  }
  return "";
}

/** The layout to save, from the header, roles and options. */
export function layout_from_roles(
  header: readonly string[],
  roles: readonly Role[],
  negate: boolean,
  date_format: string,
): QbLayout {
  const column = (role: Role) => header[roles.indexOf(role)] ?? "";
  const amount = column("amount");
  return {
    date: column("date"),
    description: column("description"),
    amount,
    debit: amount ? "" : column("debit"),
    credit: amount ? "" : column("credit"),
    negate: amount ? negate : false,
    date_format,
    balance: column("balance"),
  };
}
