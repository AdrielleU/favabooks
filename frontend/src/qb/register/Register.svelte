<script lang="ts">
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { accounts_set } from "../../stores/index.ts";
  import type { QbRegister, QbRegisterRow } from "../api.ts";
  import { put_qb_reclassify } from "../api.ts";
  import { money, short_date } from "../format.ts";

  let {
    account_name,
    register,
  }: { account_name: string; register: QbRegister | null } = $props();

  let picked = $state("");
  /** Category edits per row key; a Save button shows when one differs. */
  let edits = $state<Record<string, string>>({});
  let busy = $state(false);

  $effect.pre(() => {
    picked = account_name;
    edits = {};
  });

  const key = (row: QbRegisterRow, i: number) =>
    `${row.entry_hash}-${i.toString()}`;
  const original = (row: QbRegisterRow) => row.categories[0] ?? "";

  function open(event: SubmitEvent) {
    event.preventDefault();
    const url = new URL(window.location.href);
    url.searchParams.set("account_name", picked.trim());
    router.navigate(url);
  }

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

<form class="picker" onsubmit={open}>
  <span class="input"><AccountInput bind:value={picked} required /></span>
  <button type="submit" class="qb-primary" disabled={!picked}>
    Open register
  </button>
  {#if register}
    <span class="hint">Dates follow the Time filter in the header.</span>
    {#if ending}
      <span class="ending">
        <span>Ending balance</span>
        <strong class:negative={ending.balance < 0}>
          {money(ending.balance, ending.currency)}
        </strong>
      </span>
    {/if}
  {/if}
</form>

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
                        edits[k] = value;
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
  <p class="hint">Pick an account to open its register.</p>
{/if}

<style>
  .picker {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.75rem;
    align-items: center;
    margin-bottom: 1rem;
  }

  .picker .input {
    min-width: min(100%, 22rem);
  }

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

  .ending {
    display: flex;
    flex-direction: column;
    margin-left: auto;
    text-align: right;
  }

  .ending span {
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .ending strong {
    font-size: 1.4rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
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
</style>
