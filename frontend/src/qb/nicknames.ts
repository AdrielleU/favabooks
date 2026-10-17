/**
 * qb-fork: account nicknames ("Chase Ink Business" for
 * Liabilities:CreditCard:Card-6800), loaded whenever the ledger loads.
 */
import { derived, writable } from "svelte/store";

import { ledger_data } from "../stores/index.ts";
import { get_qb_nicknames } from "./api.ts";
import { label_for } from "./nickname-labels.ts";

/** Nicknames by account. */
export const nicknames = writable<Record<string, string>>({});

/** Reload the nicknames (after renaming an account). */
export async function refresh_nicknames(): Promise<void> {
  try {
    nicknames.set(await get_qb_nicknames());
  } catch {
    // Labels fall back to account names.
  }
}

let started = false;

/** Keep the nicknames in step with the ledger (call once at startup). */
export function start_nicknames(): void {
  if (started) {
    return;
  }
  started = true;
  ledger_data.subscribe((value: unknown) => {
    if (value !== undefined) {
      void refresh_nicknames();
    }
  });
}

/** `$account_label(account)`: the nickname, or the account's last parts. */
export const account_label = derived(
  nicknames,
  ($nicknames) => (account: string) => label_for($nicknames, account),
);

/** `$account_option(account)`: "Nickname (Account)" for select options. */
export const account_option = derived(
  nicknames,
  ($nicknames) => (account: string) => {
    const nickname = $nicknames[account];
    return nickname === undefined ? account : `${nickname} (${account})`;
  },
);
