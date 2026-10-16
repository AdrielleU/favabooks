<script lang="ts">
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import { url_for } from "../../helpers.ts";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { accounts_set } from "../../stores/index.ts";
  import type { QbAccountOverview, QbRegister, QbRegisterRow } from "../api.ts";
  import { put_qb_reclassify } from "../api.ts";
  import { money, short_date } from "../format.ts";

  let {
    account_name,
    register,
    accounts,
  }: {
    account_name: string;
    register: QbRegister | null;
    accounts: QbAccountOverview[];
  } = $props();

  /** Category edits per row key; a Save button shows when one differs. */
  /** Reset whenever a register loads. */
  let edits: Record<string, string> = $derived(register ? {} : {});
  let busy = $state(false);

  const key = (row: QbRegisterRow, i: number) =>
    `${row.entry_hash}-${i.toString()}`;
  const original = (row: QbRegisterRow) => row.categories[0] ?? "";

  function open(account: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("account_name", account);
    router.navigate(url);
  }

  const leaf = (account: string) => account.split(":").slice(1).join(":");
  let overview = $derived(accounts.find((a) => a.account === account_name));
  let options = $derived(
    accounts.some((a) => a.account === account_name) || !account_name
      ? accounts.map((a) => a.account)
      : [account_name, ...accounts.map((a) => a.account)],
  );
  let is_card = $derived(account_name.startsWith("Liabilities"));

  async function save(row: QbRegisterRow, to: string) {
    if (!$accounts_set.has(to)) {
      notify(`"${to}" is not an open account.`, "error");
      return;
    }
    busy = true;
    try {
      const res = await put_qb_reclassify({
        entry_hashes: [row.entry_hash],
        from_account: original(row),
        to_account: to,
      });
      if (res.failed[0]) {
        notify(`Could not save: ${res.failed[0].error}`, "error");
      } else {
        notify(`Moved to ${to}.`);
      }
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }
  /** QuickBooks-style column names for the account type. */
  let columns = $derived.by(() => {
    const root = register?.account.split(":")[0] ?? "";
    if (root === "Assets") {
      return { up: "Deposit", down: "Payment" };
    }
    if (root === "Liabilities") {
      return { up: "Payment", down: "Charge" };
    }
    return { up: "Debit", down: "Credit" };
  });
  let ending = $derived(register?.rows[0] ?? null);
</script>

{#if register}
  <div class="bar">
    <label class="switch">
      <span>Account</span>
      <select
        value={account_name}
        onchange={(e) => {
          open(e.currentTarget.value);
        }}
      >
        {#each options as option (option)}
          <option value={option}>{option}</option>
        {/each}
      </select>
    </label>
    {#if ending}
      <div class="stat">
        <span>{is_card ? "You owe" : "Balance"}</span>
        <strong class:negative={!is_card && ending.balance < 0}>
          {money(is_card ? -ending.balance : ending.balance, ending.currency)}
        </strong>
      </div>
    {/if}
    {#if overview}
      <div class="stat">
        <span>Transactions</span>
        <strong>{overview.transactions}</strong>
      </div>
    {/if}
    <a
      class="button qb-secondary"
      href={$url_for("qb_reconcile/", { account_name })}
    >
      Reconcile
    </a>
  </div>
  <p class="explain">
    Every transaction in this account, newest first, like a checkbook.
    {#if is_card}
      <strong>Charge</strong> adds to what you owe and <strong>Payment</strong>
      reduces it; in the Balance column, what you owe shows as a negative number.
    {:else}
      <strong>{columns.down}</strong> lowers the balance and
      <strong>{columns.up}</strong> raises it.
    {/if}
    <strong>Balance</strong> is the account's balance after each row. Click a payee
    to see or edit the transaction; change a category and press Save to move it. The
    Time filter in the header limits the dates.
  </p>
{/if}

{#if register}
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Payee and memo</th>
          <th>Category</th>
          <th class="num">{columns.down}</th>
          <th class="num">{columns.up}</th>
          <th class="num">Balance</th>
        </tr>
      </thead>
      <tbody>
        {#each register.rows as row, i (key(row, i))}
          {@const k = key(row, i)}
          {@const edited = edits[k] ?? original(row)}
          <tr>
            <td class="date">
              {short_date(row.date)}
              {#if row.flag === "!"}<span class="flag" title="Not reviewed"
                  >!</span
                >{/if}
            </td>
            <td>
              <a href={`#context-${row.entry_hash}`} title="Show and edit">
                <strong>{row.payee || row.narration}</strong>
                {#if row.payee && row.narration}
                  <span class="memo">{row.narration}</span>
                {/if}
              </a>
            </td>
            <td class="category">
              {#if row.categories.length === 1}
                <span class="edit">
                  <AccountInput
                    bind:value={
                      () => edited,
                      (value: string) => {
                        edits = { ...edits, [k]: value };
                      }
                    }
                  />
                  {#if edited !== original(row) && edited}
                    <button
                      type="button"
                      disabled={busy}
                      onclick={async () => save(row, edited)}
                    >
                      Save
                    </button>
                  {/if}
                </span>
              {:else}
                <span class="split" title={row.categories.join("\n")}>
                  {row.categories.length
                    ? `Split (${row.categories.length.toString()})`
                    : "—"}
                </span>
              {/if}
            </td>
            <td class="num">
              {row.amount < 0 ? money(-row.amount, row.currency) : ""}
            </td>
            <td class="num">
              {row.amount > 0 ? money(row.amount, row.currency) : ""}
            </td>
            <td class="num balance" class:negative={row.balance < 0}>
              {money(row.balance, row.currency)}
            </td>
          </tr>
        {:else}
          <tr><td colspan="6" class="empty">No postings in this period.</td></tr
          >
        {/each}
        {#each register.opening as opening (opening.currency)}
          <tr class="opening">
            <td></td>
            <td colspan="4">Balance forward</td>
            <td class="num balance"
              >{money(opening.amount, opening.currency)}</td
            >
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <p class="explain">
    A register lists every transaction in one bank or card account with its
    running balance, like a checkbook. Choose an account:
  </p>
  {#if accounts.length}
    <div class="choose">
      {#each accounts as a (a.account)}
        <a
          class="qb-card acct"
          href={$url_for("qb_register/", { account_name: a.account })}
        >
          <span class="acct-name">{leaf(a.account)}</span>
          <span class="muted">{a.account}</span>
          {#if a.account.startsWith("Liabilities")}
            <strong>{money(-a.balance, a.currency)}</strong>
            <span class="muted">you owe</span>
          {:else}
            <strong class:negative={a.balance < 0}>
              {money(a.balance, a.currency)}
            </strong>
          {/if}
          <span class="muted">
            {a.transactions} transactions{a.last_date
              ? ` · last ${short_date(a.last_date)}`
              : ""}
          </span>
        </a>
      {/each}
    </div>
  {:else}
    <p class="hint">No bank or card accounts with transactions yet.</p>
  {/if}
{/if}

<style>
  .hint,
  .memo,
  .split,
  .empty {
    color: var(--text-color-lightest);
  }

  /* No overflow clipping: account suggestion lists open below a row and
   * must stay visible (the page scrolls instead). */
  .table-card {
    padding: 0;
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0;
    border: none;
  }

  th,
  td {
    padding: 0.45em 0.75em;
    vertical-align: middle;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-weight: 500;
    color: var(--text-color-lighter);
    text-align: left;
    background: var(--background-darker);
  }

  .date,
  .num {
    white-space: nowrap;
  }

  .num {
    text-align: right;
  }

  .balance {
    font-weight: 500;
  }

  .negative {
    color: var(--diff-negative);
  }

  .flag {
    margin-left: 0.3em;
    font-weight: 600;
    color: var(--warning);
  }

  td a {
    color: inherit;
  }

  td a strong {
    font-weight: 500;
  }

  .memo {
    display: block;
    font-size: 0.9em;
  }

  .category {
    min-width: 15rem;
  }

  /* Category boxes read as text until hovered or focused. */
  .category :global(input) {
    background: transparent;
    border-color: transparent;
  }

  tr:hover .category :global(input),
  .category :global(input:focus) {
    background: var(--qb-surface);
    border-color: var(--border-darker);
  }

  .edit {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  .opening td {
    font-style: italic;
    background: var(--background-darker);
  }

  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 2rem;
    align-items: flex-end;
    margin-bottom: 0.6rem;
  }

  .switch,
  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .switch span,
  .stat span {
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .stat strong {
    font-size: 1.35rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .bar .button {
    margin-left: auto;
  }

  .explain {
    max-width: 60rem;
    margin: 0 0 1rem;
    color: var(--text-color-lighter);
  }

  .choose {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 16rem), 1fr));
    gap: 1rem;
  }

  .acct {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    color: inherit;
  }

  .acct:hover {
    border-color: var(--qb-accent);
  }

  .acct-name {
    font-weight: 600;
  }

  .acct strong {
    margin-top: 0.4rem;
    font-size: 1.4rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .muted {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }
</style>
