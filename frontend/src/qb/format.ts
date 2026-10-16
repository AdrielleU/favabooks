/**
 * Money and date formatting for Favabooks pages: "$1,234.56" rather than
 * Fava's "1234.56 USD", like QuickBooks. Uses the browser's locale.
 */

const formatters = new Map<string, Intl.NumberFormat>();

function formatter(currency: string): Intl.NumberFormat | null {
  let fmt = formatters.get(currency);
  if (fmt === undefined) {
    try {
      fmt = new Intl.NumberFormat(undefined, { style: "currency", currency });
    } catch {
      // Not an ISO currency (e.g. a stock ticker or a custom commodity).
      return null;
    }
    formatters.set(currency, fmt);
  }
  return fmt;
}

/** Format an amount, e.g. "$1,234.56" or "-$12.00"; "12 AAPL" otherwise. */
export function money(amount: number, currency: string): string {
  const fmt = formatter(currency);
  return fmt ? fmt.format(amount) : `${amount.toLocaleString()} ${currency}`;
}

/** Format a whole-number amount for big headline figures, e.g. "$1,235". */
export function money_short(amount: number, currency: string): string {
  const fmt = formatter(currency);
  if (!fmt) {
    return money(amount, currency);
  }
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** "Sep 14, 2026" for a UTC date (Beancount dates have no time zone). */
export function short_date(date: Date): string {
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Percentage change from `previous` to `current`, or null if undefined. */
export function change(current: number, previous: number): number | null {
  return previous === 0 ? null : (current - previous) / Math.abs(previous);
}
