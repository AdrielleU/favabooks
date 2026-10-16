/**
 * qb-fork: date periods, aging, sorting and CSV for the Invoices/Bills and
 * Customers/Vendors pages (no DOM imports, so they can be unit tested).
 * Dates are UTC, like Beancount's.
 */

export interface Period {
  key: string;
  label: string;
  /** Inclusive "YYYY-MM-DD" bounds ("" for open-ended). */
  start: string;
  end: string;
}

/** "YYYY-MM-DD" of a UTC date. */
export function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

const utc = (y: number, m: number, d: number) => new Date(Date.UTC(y, m, d));
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** A calendar month "YYYY-MM" as a period. */
export function month_period(key: string): Period | null {
  const match = /^(\d{4})-(\d{2})$/.exec(key);
  if (!match) {
    return null;
  }
  const y = Number(match[1]);
  const m = Number(match[2]) - 1;
  if (m < 0 || m > 11) {
    return null;
  }
  return {
    key,
    label: `${MONTHS[m] ?? ""} ${y.toString()}`,
    start: iso(utc(y, m, 1)),
    end: iso(utc(y, m + 1, 0)),
  };
}

/** The preset periods relative to `today`. */
export function presets(today: Date): Period[] {
  const y = today.getUTCFullYear();
  const m = today.getUTCMonth();
  const q = Math.floor(m / 3) * 3;
  const range = (
    key: string,
    label: string,
    start: Date | null,
    end: Date | null,
  ): Period => ({
    key,
    label,
    start: start ? iso(start) : "",
    end: end ? iso(end) : "",
  });
  return [
    range("all", "All dates", null, null),
    range("this-month", "This month", utc(y, m, 1), utc(y, m + 1, 0)),
    range("last-month", "Last month", utc(y, m - 1, 1), utc(y, m, 0)),
    range("this-quarter", "This quarter", utc(y, q, 1), utc(y, q + 3, 0)),
    range("last-quarter", "Last quarter", utc(y, q - 3, 1), utc(y, q, 0)),
    range("this-year", "This year", utc(y, 0, 1), utc(y, 11, 31)),
    range("last-year", "Last year", utc(y - 1, 0, 1), utc(y - 1, 11, 31)),
    range("last-12", "Last 12 months", utc(y, m - 11, 1), utc(y, m + 1, 0)),
  ];
}

/** Months that have dates, newest first, as "YYYY-MM" periods. */
export function data_months(dates: readonly Date[]): Period[] {
  const keys = [...new Set(dates.map((d) => iso(d).slice(0, 7)))].sort();
  return keys
    .reverse()
    .map(month_period)
    .filter((p): p is Period => p !== null);
}

/** Years that have dates, newest first. */
export function data_years(dates: readonly Date[]): Period[] {
  const years = [...new Set(dates.map((d) => d.getUTCFullYear()))].sort();
  return years.reverse().map((y) => ({
    key: y.toString(),
    label: y.toString(),
    start: `${y.toString()}-01-01`,
    end: `${y.toString()}-12-31`,
  }));
}

/** Resolve the `period` URL value (and custom from/to) to a Period. */
export function resolve_period(
  key: string,
  from: string,
  to: string,
  today: Date,
): Period {
  if (key === "custom") {
    return { key, label: "Custom", start: from, end: to };
  }
  if (/^\d{4}$/.test(key)) {
    return { key, label: key, start: `${key}-01-01`, end: `${key}-12-31` };
  }
  const month = month_period(key);
  if (month) {
    return month;
  }
  return (
    presets(today).find((p) => p.key === key) ?? {
      key: "all",
      label: "All dates",
      start: "",
      end: "",
    }
  );
}

/** Whether `date` is in the inclusive period. */
export function in_period(date: Date, period: Period): boolean {
  const d = iso(date);
  return (
    (period.start === "" || d >= period.start) &&
    (period.end === "" || d <= period.end)
  );
}

export const AGING_BUCKETS = [
  "Current",
  "1–30 days",
  "31–60 days",
  "61–90 days",
  "91+ days",
] as const;

/**
 * Unpaid balances in cents by days past due: current (not due yet, or no
 * due date), 1–30, 31–60, 61–90 and 91+.
 */
export function aging(
  docs: readonly { balance: number; due: Date | null; status: string }[],
  today: Date,
): number[] {
  const buckets = [0, 0, 0, 0, 0];
  for (const doc of docs) {
    if (doc.status === "paid" || doc.balance <= 0) {
      continue;
    }
    const late =
      doc.due === null
        ? 0
        : Math.round((today.getTime() - doc.due.getTime()) / 86_400_000);
    const i =
      late <= 0 ? 0 : late <= 30 ? 1 : late <= 60 ? 2 : late <= 90 ? 3 : 4;
    buckets[i] = (buckets[i] ?? 0) + Math.round(doc.balance * 100);
  }
  return buckets;
}

type Sortable = string | number | Date | null;

/** Rows sorted by `key(row)`; nulls last, either direction. */
export function sort_by<T>(
  rows: readonly T[],
  key: (row: T) => Sortable,
  descending: boolean,
): T[] {
  const value = (v: Sortable) => (v instanceof Date ? v.getTime() : v);
  return [...rows].sort((a, b) => {
    const x = value(key(a));
    const y = value(key(b));
    if (x === y) {
      return 0;
    }
    if (x === null) {
      return 1;
    }
    if (y === null) {
      return -1;
    }
    const order =
      typeof x === "string" && typeof y === "string"
        ? x.localeCompare(y)
        : x < y
          ? -1
          : 1;
    return descending ? -order : order;
  });
}

/** CSV text for rows of cells (RFC 4180 quoting). */
export function to_csv(
  rows: readonly (readonly (string | number)[])[],
): string {
  const cell = (value: string | number) => {
    const text = value.toString();
    return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  return `${rows.map((row) => row.map(cell).join(",")).join("\n")}\n`;
}

/**
 * The 1099-NEC reporting threshold for payments in `period`: $600 through
 * 2025, $2,000 from 2026 (One Big Beautiful Bill Act; indexed for
 * inflation from 2027, so check the IRS instructions for later years).
 */
export function nec_threshold(period: Period, today: Date): number {
  const end = period.end || iso(today);
  return Number(end.slice(0, 4)) >= 2026 ? 2000 : 600;
}
