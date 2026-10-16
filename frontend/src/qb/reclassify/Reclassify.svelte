<!--
  qb-fork: Bulk reclassify. Pick a category, narrow the list, tick
  transactions and move them all to another category at once.
-->
<script lang="ts">
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { accounts_set } from "../../stores/index.ts";
  import type { QbCategory, QbPostings } from "../api.ts";
  import { put_qb_reclassify } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import { leaf } from "../transactions/helpers.ts";
  import { navigate_with, type ReclassifySearch } from "./search.ts";

  let {
    search,
    result,
    categories,
  }: {
    search: ReclassifySearch;
    result: QbPostings | null;
    categories: QbCategory[];
  } = $props();

  // Form fields start from the URL and are edited locally until Search.
  let form = $state<ReclassifySearch>({
    account_name: "",
    payee: "",
    min_amount: "",
    max_amount: "",
  });
  let other_account = $state("");
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
  let hashes = $derived([...new Set(rows.map((r) => r.entry_hash))]);
  let selected_hashes = $derived(hashes.filter((h) => selected[h] === true));
  let all_selected = $derived(
    hashes.length > 0 && selected_hashes.length === hashes.length,
  );
  let selected_total = $derived(
    rows
      .filter((r) => selected[r.entry_hash] === true)
      .reduce((sum, r) => sum + Math.round(r.amount * 100), 0) / 100,
  );
  let currency = $derived(
    rows[0]?.currency ?? categories[0]?.currency ?? "USD",
  );
  /** One-click targets: the most used categories other than this one. */
  let quick_targets = $derived(
    categories
      .map((c) => c.account)
      .filter((a) => a !== search.account_name)
      .slice(0, 6),
  );
  let filtered = $derived(
    search.payee !== "" || search.min_amount !== "" || search.max_amount !== "",
  );

  function submit(next: ReclassifySearch) {
    const trimmed = navigate_with(next);
    form = { ...trimmed };
    submitted = JSON.stringify(trimmed);
  }

  function pick(account: string) {
    submit({
      account_name: account,
      payee: "",
      min_amount: "",
      max_amount: "",
    });
  }

  function run_search(event: SubmitEvent) {
    event.preventDefault();
    submit(form);
  }

  function select_all(value: boolean) {
    selected = Object.fromEntries(hashes.map((h) => [h, value]));
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

<p class="intro">
  Move many transactions from one category to another at once, for example every
  Amazon purchase filed under Office into Equipment.
</p>

<section class="qb-card step">
  <h3><span class="step-no">1</span> Pick the category to clean up</h3>
  {#if categories.length}
    <div class="chips">
      {#each categories as c (c.account)}
        <button
          type="button"
          class="chip"
          class:active={c.account === search.account_name}
          class:attention={c.account.endsWith("Uncategorized")}
          title={c.account}
          onclick={() => {
            pick(c.account);
          }}
        >
          <span class="chip-name">{leaf(c.account)}</span>
          <span class="chip-meta">{c.count} · {money(c.total, c.currency)}</span
          >
        </button>
      {/each}
    </div>
  {:else}
    <p class="muted">No income or expense categories in the current filters.</p>
  {/if}
  <form
    class="other"
    onsubmit={(e) => {
      e.preventDefault();
      if (other_account) {
        pick(other_account);
      }
    }}
  >
    <span class="muted">or any account:</span>
    <span class="other-input"><AccountInput bind:value={other_account} /></span>
    <button type="submit" class="qb-secondary" disabled={!other_account}>
      Open
    </button>
  </form>
</section>

{#if result}
  <section class="qb-card step">
    <h3>
      <span class="step-no">2</span> Narrow it down
      <span class="muted">(optional)</span>
    </h3>
    <form class="filters" onsubmit={run_search}>
      <label>
        <span>Payee or description contains</span>
        <input type="text" bind:value={form.payee} placeholder="e.g. amazon" />
      </label>
      <label class="amount">
        <span>Amount from</span>
        <input
          type="text"
          inputmode="decimal"
          placeholder="0.00"
          bind:value={form.min_amount}
        />
      </label>
      <label class="amount">
        <span>to</span>
        <input
          type="text"
          inputmode="decimal"
          placeholder="any"
          bind:value={form.max_amount}
        />
      </label>
      <button type="submit" class="qb-primary">
        <Icon name="search" size={15} /> Filter
      </button>
      {#if filtered}
        <button
          type="button"
          class="link"
          onclick={() => {
            pick(search.account_name);
          }}>Clear filters</button
        >
      {/if}
    </form>
  </section>

  <section class="step-head">
    <h3>
      <span class="step-no">3</span> Tick transactions to move
      <span class="muted">
        — {result.total} in <strong>{search.account_name}</strong>
        {#if result.total > rows.length}(showing the newest {rows.length}){/if}
      </span>
    </h3>
    {#if rows.length}
      <div class="select-buttons">
        <button
          type="button"
          class="qb-secondary small"
          disabled={all_selected}
          onclick={() => {
            select_all(true);
          }}>Select all</button
        >
        <button
          type="button"
          class="qb-secondary small"
          disabled={!selected_hashes.length}
          onclick={() => {
            select_all(false);
          }}>Clear selection</button
        >
      </div>
    {/if}
  </section>

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
                onchange={(e) => {
                  select_all(e.currentTarget.checked);
                }}
              />
            </th>
            <th>Date</th>
            <th>Payee</th>
            <th>Paid with / other accounts</th>
            <th class="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row, i (`${row.entry_hash}-${i.toString()}`)}
            {@const id = `rc-${row.entry_hash}-${i.toString()}`}
            <tr class:selected={selected[row.entry_hash]}>
              <td class="check">
                <input
                  type="checkbox"
                  {id}
                  bind:checked={
                    () => selected[row.entry_hash] === true,
                    (value: boolean) => {
                      selected[row.entry_hash] = value;
                    }
                  }
                />
              </td>
              <td class="date">
                <label class="row-label" for={id}>{short_date(row.date)}</label>
              </td>
              <td>
                <label class="row-label" for={id}>
                  <strong>{row.payee || row.narration}</strong>
                  {#if row.payee && row.narration}
                    <span class="narration">{row.narration}</span>
                  {/if}
                </label>
              </td>
              <td class="others">{row.others.map(leaf).join(", ")}</td>
              <td class="num">{money(row.amount, row.currency)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="qb-card muted">Nothing matches these filters.</p>
  {/if}
{:else}
  <p class="muted pick-hint">
    <Icon name="arrow-right" size={15} /> Pick a category above to list its transactions.
  </p>
{/if}

{#if selected_hashes.length}
  <div class="action-bar">
    <div class="action-inner">
      <span class="action-count">
        <strong>{selected_hashes.length}</strong> selected ·
        {money(selected_total, currency)}
      </span>
      <span class="muted">Move to</span>
      <span class="picker"><AccountInput bind:value={move_to} /></span>
      <button
        type="button"
        class="qb-primary"
        disabled={busy || !move_to || move_to === search.account_name}
        onclick={apply}
      >
        Move {selected_hashes.length}
      </button>
      <button
        type="button"
        class="link"
        onclick={() => {
          select_all(false);
        }}>Cancel</button
      >
      {#if quick_targets.length}
        <span class="quick">
          <span class="muted">Quick pick:</span>
          {#each quick_targets as target (target)}
            <button
              type="button"
              class="quick-chip"
              class:active={move_to === target}
              title={target}
              onclick={() => {
                move_to = target;
              }}>{leaf(target)}</button
            >
          {/each}
        </span>
      {/if}
    </div>
  </div>
{/if}

<style>
  .intro {
    max-width: 60rem;
    margin: 0 0 1rem;
    color: var(--text-color-lighter);
  }

  .muted {
    color: var(--qb-muted);
  }

  .step {
    margin-bottom: 1rem;
  }

  h3 {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin: 0 0 0.75rem;
    font-size: 1rem;
  }

  h3 .muted {
    font-weight: 400;
  }

  .step-no {
    display: inline-grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    font-size: 0.85rem;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .chip {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 0.45rem 0.8rem;
    color: var(--text-color);
    text-align: left;
    background: var(--qb-surface);
    border: 1px solid var(--border);
    border-radius: 10px;
  }

  .chip:hover {
    border-color: var(--qb-accent);
  }

  .chip.attention {
    border-color: var(--warning);
  }

  .chip.active {
    background: var(--qb-accent-soft);
    border-color: var(--qb-accent);
  }

  .chip-name {
    font-weight: 600;
  }

  .chip-meta {
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .other {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin-top: 0.9rem;
  }

  .other-input {
    min-width: min(100%, 18rem);
  }

  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
    align-items: end;
  }

  .filters label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .filters label span {
    font-size: 0.85em;
    color: var(--text-color-lighter);
  }

  .amount input {
    width: 7rem;
  }

  .filters .qb-primary {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
  }

  .step-head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.6rem;
  }

  .step-head h3 {
    margin: 0;
  }

  .select-buttons {
    display: flex;
    gap: 0.5rem;
  }

  .small {
    padding: 0.3em 0.9em;
    font-size: 0.88em;
  }

  .link {
    padding: 0;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }

  .pick-hint {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  /* No overflow clipping: account suggestion lists open below a row and
   * must stay visible (the page scrolls instead). */
  .table-card {
    padding: 0;
    margin-bottom: 5rem;
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

  .row-label {
    display: block;
    cursor: pointer;
  }

  .row-label strong {
    font-weight: 500;
  }

  .check {
    width: 1px;
  }

  .date,
  .num {
    white-space: nowrap;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .narration,
  .others {
    color: var(--qb-muted);
  }

  .narration {
    display: block;
    font-size: 0.9em;
  }

  .action-bar {
    position: sticky;
    bottom: 0;
    z-index: 5;
    padding-bottom: env(safe-area-inset-bottom, 0);
    margin-top: -4rem;
  }

  .action-inner {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.75rem;
    align-items: center;
    padding: 0.75rem 1rem;
    background: var(--qb-surface);
    border: 1px solid var(--qb-accent);
    border-radius: 12px;
    box-shadow: 0 -4px 16px rgb(0 0 0 / 12%);
  }

  .action-count {
    margin-right: 0.5rem;
  }

  .picker {
    min-width: min(100%, 16rem);
  }

  .quick {
    display: flex;
    flex-basis: 100%;
    flex-wrap: wrap;
    gap: 0.35rem;
    align-items: center;
    font-size: 0.88em;
  }

  .quick-chip {
    padding: 0.15em 0.7em;
    color: var(--text-color);
    background: var(--background-darker);
    border-radius: 999px;
  }

  .quick-chip.active {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }
</style>
