/** qb-fork: account labels with nicknames (no DOM, so it can be tested). */

/**
 * The nickname of `account`, or its name without the root
 * ("Liabilities:CreditCard:Card-6800" -> "CreditCard:Card-6800").
 */
export function label_for(
  nicknames: Readonly<Record<string, string>>,
  account: string,
): string {
  const nickname = nicknames[account];
  if (nickname !== undefined) {
    return nickname;
  }
  const i = account.indexOf(":");
  return i === -1 ? account : account.slice(i + 1);
}
