/**
 * qb-fork: pure helpers for the Reconcile page (no DOM imports, so they can
 * be unit tested). Amounts are handled in whole cents to avoid float drift.
 */

/** Whole cents for an amount. */
export function cents(amount: number): number {
  return Math.round(amount * 100);
}

/** "-12.50" for -1250 cents. */
export function cents_string(value: number): string {
  return (value / 100).toFixed(2);
}

/**
 * Sign that turns ledger amounts into what a statement prints: a card
 * statement shows what you owe as a positive balance, the ledger as negative.
 */
export function statement_sign(account: string): 1 | -1 {
  return account.startsWith("Liabilities") ? -1 : 1;
}

/**
 * Parse a statement balance as typed ("$1,234.56", "(12.00)", "-5"), in
 * cents, or null if it isn't a number.
 */
export function parse_amount(text: string): number | null {
  let t = text.trim().replace(/[$,\s]/g, "");
  let negative = false;
  if (/^\(.*\)$/.test(t)) {
    negative = true;
    t = t.slice(1, -1);
  }
  if (!/^-?\d+(\.\d{0,2})?$|^-?\.\d{1,2}$/.test(t)) {
    return null;
  }
  const value = Math.round(Number.parseFloat(t) * 100);
  return negative ? -value : value;
}

/** Statement ending balance minus what is cleared, in cents (ledger sign). */
export function difference(
  ending: number,
  beginning: number,
  ticked: readonly number[],
): number {
  return ticked.reduce((rest, amount) => rest - amount, ending - beginning);
}
