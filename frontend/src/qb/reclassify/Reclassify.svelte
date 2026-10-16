<script lang="ts">
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { accounts_set } from "../../stores/index.ts";
  import type { QbPostings } from "../api.ts";
  import { put_qb_reclassify } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import { navigate_with, type ReclassifySearch } from "./search.ts";

  let {
    search,
    result,
  }: { search: ReclassifySearch; result: QbPostings | null } = $props();

  // Form fields start from the URL and are edited locally until Search.
  let form = $state<ReclassifySearch>({
    account_name: "",
    payee: "",
    min_amount: "",
    max_amount: "",
  });
  let selected = $state<Record<string, boolean>>({});
  let move_to = $state("");
  let busy = $state(false);

  // The search this form last submitted. When the page reloads with that
  // search, keep the form as is so typing during a load isn't lost; any
  // other URL (back/forward, a shared link) resets the form to match it.
  let submitted = "";

  $effect.pre(() => {
    if (JSON.stringify(search) !== submitted) {
      form = { ...search };
    }
    selected = {};
  });

  let rows = $derived(result?.rows ?? []);
  let selected_hashes = $derived(
    [...new Set(rows.map((r) => r.entry_hash))].filter(
      (hash) => selected[hash] === true,
    ),
  );
  let all_selected = $derived(
    rows.length > 0 && rows.every((r) => selected[r.entry_hash] === true),
  );

  function toggle_all() {
    const value = !all_selected;
    selected = Object.fromEntries(rows.map((r) => [r.entry_hash, value]));
  }

  function run_search(event: SubmitEvent) {
    event.preventDefault();
    submitted = JSON.stringify(navigate_with(form));
  }

  async function apply() {
    if (!$accounts_set.has(move_to)) {
      notify(`"${move_to}" is not an open account.`, "error");
      return;
    }
    busy = true;
    try {
      const res = await put_qb_reclassify({
        entry_hashes: selected_hashes,
        from_account: search.account_name,
        to_account: move_to,
      });
      notify(
        `Moved ${res.changed.toString()} transaction${res.changed === 1 ? "" : "s"} to ${move_to}.`,
      );
      if (res.failed[0]) {
        notify(
          `${res.failed.length.toString()} could not be saved: ${res.failed[0].error}`,
          "error",
        );
      }
      move_to = "";
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }
</script>

<form class="qb-card filters" onsubmit={run_search}>
  <label class="account">
    <span>Account</span>
    <AccountInput bind:value={form.account_name} required />
  </label>
  <label>
    <span>Payee or description contains</span>
    <input type="text" bind:value={form.payee} placeholder="e.g. amazon" />
  </label>
  <label class="amount">
    <span>Amount from</span>
    <input type="text" inputmode="decimal" bind:value={form.min_amount} />
  </label>
  <label class="amount">
    <span>to</span>
    <input type="text" inputmode="decimal" bind:value={form.max_amount} />
  </label>
  <button type="submit" class="qb-primary" disabled={!form.account_name}>
    Search
  </button>
  <p class="hint form-hint">
    Dates come from the Time filter in the header. Amounts match either sign.
  </p>
</form>

{#if result}
  <div class="toolbar">
    <span>
      {result.total} posting{result.total === 1 ? "" : "s"} in
      <strong>{search.account_name}</strong>
      {#if result.total > rows.length}
        (showing the newest {rows.length}; narrow the filters to see the rest)
      {/if}
    </span>
    {#if selected_hashes.length}
      <span class="move">
        Move {selected_hashes.length} to
        <span class="picker"><AccountInput bind:value={move_to} /></span>
        <button
          type="button"
          class="qb-primary"
          disabled={busy || !move_to || move_to === search.account_name}
          onclick={apply}
        >
          Apply
        </button>
      </span>
    {/if}
  </div>

  {#if rows.length}
    <div class="qb-card table-card">
      <table>
        <thead>
          <tr>
            <th class="check">
              <input
                type="checkbox"
                aria-label="Select all"
                checked={all_selected}
                onchange={toggle_all}
              />
            </th>
            <th>Date</th>
            <th>Description</th>
            <th>Other accounts</th>
            <th class="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row, i (`${row.entry_hash}-${i.toString()}`)}
            <tr class:selected={selected[row.entry_hash]}>
              <td class="check">
                <input
                  type="checkbox"
                  aria-label="Select"
                  bind:checked={
                    () => selected[row.entry_hash] === true,
                    (value: boolean) => {
                      selected[row.entry_hash] = value;
                    }
                  }
                />
              </td>
              <td class="date">
                {short_date(row.date)}
                {#if row.flag === "!"}<span class="flag" title="Not reviewed"
                    >!</span
                  >{/if}
              </td>
              <td>
                <a href={`#context-${row.entry_hash}`} title="Show transaction">
                  <strong>{row.payee || row.narration}</strong>
                  {#if row.payee && row.narration}
                    <span class="narration">{row.narration}</span>
                  {/if}
                </a>
              </td>
              <td class="others">{row.others.join(", ")}</td>
              <td class="num">{money(row.amount, row.currency)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{:else}
  <p class="hint">Pick an account to list its postings.</p>
{/if}

<style>
  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
    align-items: end;
    margin-bottom: 1rem;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  label span {
    font-size: 0.85em;
    color: var(--text-color-lighter);
  }

  .account {
    min-width: min(100%, 18rem);
  }

  .amount input {
    width: 7rem;
  }

  .form-hint {
    flex-basis: 100%;
    margin: 0;
  }

  .hint,
  .narration,
  .others {
    color: var(--text-color-lightest);
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
    align-items: center;
    justify-content: space-between;
    min-height: 2.4rem;
    margin-bottom: 0.75rem;
  }

  .move {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  .picker {
    min-width: 16rem;
  }

  .table-card {
    padding: 0;
    overflow-x: auto;
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0;
    border: none;
  }

  th,
  td {
    padding: 0.5em 0.75em;
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

  tr.selected td {
    background: color-mix(in srgb, var(--qb-accent) 8%, transparent);
  }

  .check {
    width: 1px;
  }

  .date,
  .num {
    white-space: nowrap;
  }

  .num {
    text-align: right;
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

  .narration {
    display: block;
    font-size: 0.9em;
  }
</style>
