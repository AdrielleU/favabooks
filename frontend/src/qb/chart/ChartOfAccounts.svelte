<!--
  qb-fork: Chart of accounts. Every account by QuickBooks-style type, with
  its balance and activity; add or close accounts.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import type { QbChart, QbChartAccount } from "../api.ts";
  import { put_qb_account_close } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import { path_parts, type_rank } from "./helpers.ts";
  import NewAccount from "./NewAccount.svelte";

  let { chart }: { chart: QbChart } = $props();

  const TABS: [string, string][] = [
    ["", "All"],
    ["assets", "Assets"],
    ["liabilities", "Liabilities"],
    ["equity", "Equity"],
    ["income", "Income"],
    ["expenses", "Expenses"],
  ];
  let tab = $state("");
  let query = $state("");
  let show_closed = $state(false);
  let adding = $state(false);
  let closing = $state<QbChartAccount | null>(null);
  let close_date = $state("");
  let busy = $state(false);

  let roots = $derived(chart.roots);
  let year = $derived(chart.year_start.getUTCFullYear());
  const root_of = (account: string) => account.split(":")[0] ?? "";
  let is_pnl = $derived((account: string) =>
    [roots.income, roots.expenses].includes(root_of(account)),
  );
  let visible = $derived(
    chart.accounts.filter(
      (a) =>
        (show_closed || a.close_date === null) &&
        (tab === "" || root_of(a.account) === roots[tab]) &&
        `${a.account} ${a.type} ${a.detail_type}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
    ),
  );
  let groups = $derived(
    [...new Set(visible.map((a) => a.type))]
      .sort((a, b) => type_rank(a) - type_rank(b))
      .map((type) => ({
        type,
        accounts: visible.filter((a) => a.type === type),
      })),
  );
  let counts = $derived(
    Object.fromEntries(
      TABS.map(([key]) => [
        key,
        chart.accounts.filter(
          (a) =>
            (show_closed || a.close_date === null) &&
            (key === "" || root_of(a.account) === roots[key]),
        ).length,
      ]),
    ),
  );
  let names = $derived(new Set(chart.accounts.map((a) => a.account)));
  let closed_count = $derived(
    chart.accounts.filter((a) => a.close_date !== null).length,
  );

  /** Balances as people read them: what you owe and earn as positive. */
  const shown = (a: QbChartAccount) =>
    [roots.liabilities, roots.equity, roots.income].includes(root_of(a.account))
      ? -a.balance + 0
      : a.balance;
  const is_money = (a: QbChartAccount) =>
    [roots.assets, roots.liabilities].includes(root_of(a.account));

  function start_close(a: QbChartAccount) {
    closing = a;
    close_date = new Date().toISOString().slice(0, 10);
  }

  async function close() {
    if (!closing) {
      return;
    }
    busy = true;
    try {
      notify(
        await put_qb_account_close({
          account: closing.account,
          date: close_date,
        }),
      );
      closing = null;
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }
</script>

<div class="page-head">
  <p class="muted">
    Every account in your books, grouped like QuickBooks. Balances for income
    and expenses are for {year}; bank, card and other balance sheet accounts
    show their balance today.
  </p>
  <button type="button" class="qb-primary" onclick={() => (adding = true)}>
    <Icon name="plus" size={16} /> New account
  </button>
</div>

<div class="toolbar">
  <div class="tabs" role="tablist">
    {#each TABS as [key, label] (key)}
      <button
        type="button"
        role="tab"
        aria-selected={tab === key}
        class:active={tab === key}
        onclick={() => (tab = key)}
      >
        {label} <span class="count">{counts[key]}</span>
      </button>
    {/each}
  </div>
  <div class="right">
    {#if closed_count}
      <label class="check">
        <input type="checkbox" bind:checked={show_closed} /> Show closed ({closed_count})
      </label>
    {/if}
    <label class="search">
      <Icon name="search" size={16} />
      <input type="search" placeholder="Search accounts…" bind:value={query} />
    </label>
  </div>
</div>

{#if groups.length}
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Detail type</th>
          <th class="num">Balance</th>
          <th class="num">Transactions</th>
          <th>Last activity</th>
          <th class="actions-col"></th>
        </tr>
      </thead>
      {#each groups as group (group.type)}
        <tbody>
          <tr class="group-row">
            <td colspan="6">{group.type}</td>
          </tr>
          {#each group.accounts as a (a.account)}
            {@const parts = path_parts(a.account)}
            {@const nested = names.has(
              a.account.split(":").slice(0, -1).join(":"),
            )}
            <tr class:closed={a.close_date !== null}>
              <td>
                <span
                  class="indent"
                  style:padding-left={nested ? "1.1rem" : "0"}
                >
                  <strong
                    >{nested
                      ? (parts[parts.length - 1] ?? a.account)
                      : parts.join(": ")}</strong
                  >
                </span>
                <span class="muted sub">{a.account}</span>
                {#if a.close_date}
                  <span class="badge">Closed {short_date(a.close_date)}</span>
                {/if}
              </td>
              <td class="muted">{a.detail_type}</td>
              <td class="num">
                {money(shown(a), chart.currency)}
                {#if is_pnl(a.account)}<span class="muted sub">{year}</span
                  >{/if}
              </td>
              <td class="num">{a.transactions || "—"}</td>
              <td class="nowrap"
                >{a.last_date ? short_date(a.last_date) : "—"}</td
              >
              <td class="actions-col">
                {#if is_money(a)}
                  <a
                    href={$url_for("qb_register/", { account_name: a.account })}
                    >Register</a
                  >
                {:else}
                  <a href={$url_for("qb_transactions/", { account: a.account })}
                    >Transactions</a
                  >
                {/if}
                <a
                  href={$url_for(`account/${a.account}/`)}
                  title="Fava's account page with charts and balances"
                  >Details</a
                >
                {#if a.close_date === null}
                  <button
                    type="button"
                    class="link"
                    onclick={() => {
                      start_close(a);
                    }}>Close</button
                  >
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      {/each}
    </table>
  </div>
{:else}
  <p class="qb-card muted">No accounts match.</p>
{/if}

{#if closing}
  <div class="qb-card confirm">
    <p>
      Close <strong>{closing.account}</strong>? It stays in past reports, but no
      new transactions can use it after the closing date. Its balance must be
      zero.
    </p>
    <label>
      Closing date <input type="date" bind:value={close_date} />
    </label>
    <div class="confirm-actions">
      <button
        type="button"
        class="qb-secondary"
        onclick={() => (closing = null)}>Cancel</button
      >
      <button
        type="button"
        class="qb-primary danger"
        disabled={busy || !close_date}
        onclick={close}
      >
        Close account
      </button>
    </div>
  </div>
{/if}

{#if adding}
  <NewAccount
    {chart}
    onclose={() => (adding = false)}
    ondone={() => {
      adding = false;
      router.reload();
    }}
  />
{/if}

<style>
  .page-head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .page-head p {
    max-width: 46rem;
    margin: 0;
  }

  .page-head button {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
  }

  .muted {
    color: var(--qb-muted);
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.6rem;
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .tabs button {
    padding: 0.35em 0.9em;
    font-weight: 500;
    color: var(--text-color);
    background: var(--qb-surface);
    border: 1px solid var(--border);
    border-radius: 999px;
  }

  .tabs button.active {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-color: var(--qb-accent);
  }

  .count {
    font-size: 0.8em;
    color: var(--qb-muted);
  }

  .right {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1rem;
    align-items: center;
  }

  .check {
    display: flex;
    gap: 0.35rem;
    align-items: center;
  }

  .search {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    padding: 0 0.6rem;
    color: var(--qb-muted);
    background: var(--qb-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  .search input {
    width: min(16rem, 60vw);
    padding: 0.45em 0;
    outline: none;
    background: none;
    border: none;
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
    vertical-align: top;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-weight: 500;
    color: var(--text-color-lighter);
    text-align: left;
    background: var(--background-darker);
  }

  .group-row td {
    padding-top: 0.9em;
    font-size: 0.85em;
    font-weight: 700;
    color: var(--text-color-lighter);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    background: var(--background);
  }

  .indent {
    display: block;
  }

  .indent strong {
    font-weight: 550;
  }

  .sub {
    display: block;
    font-size: 0.8em;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }

  .nowrap {
    white-space: nowrap;
  }

  tr.closed td {
    opacity: 0.6;
  }

  .badge {
    display: inline-block;
    padding: 0 0.5em;
    margin-top: 0.2em;
    font-size: 0.75em;
    background: var(--background-darker);
    border-radius: 999px;
  }

  .actions-col {
    white-space: nowrap;
  }

  .link {
    padding: 0;
    background: none;
  }

  .actions-col a,
  .actions-col .link {
    margin-right: 0.7rem;
    font-size: 0.9em;
    font-weight: 600;
    color: var(--qb-accent);
  }

  .confirm {
    position: sticky;
    bottom: 1rem;
    z-index: 5;
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1rem;
    align-items: center;
    margin-top: 1rem;
    border: 1px solid var(--warning);
  }

  .confirm p {
    flex-basis: 100%;
    margin: 0;
  }

  .confirm label {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  .confirm-actions {
    display: flex;
    gap: 0.5rem;
    margin-left: auto;
  }

  .danger {
    background: var(--error);
    border-color: var(--error);
  }
</style>
