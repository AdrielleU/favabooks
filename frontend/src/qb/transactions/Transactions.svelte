<!--
  qb-fork: All transactions. Every transaction in the header filters, newest
  first, with its type, category, the account it was paid with, the amount,
  and its receipt.
-->
<script lang="ts">
  import { url_for, url_for_raw } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import { KIND_TABS, kind_label, leaf, totals } from "./helpers.ts";
  import type { TransactionsProps } from "./index.ts";

  let { search, kind, result }: TransactionsProps = $props();

  let query = $derived(search);
  let rows = $derived(result.rows);
  let currency = $derived(rows[0]?.currency ?? "USD");
  let sums = $derived(totals(rows));
  let tabs = $derived(
    KIND_TABS.filter(
      ([k]) =>
        k === "" || k === kind || k === "review" || (result.counts[k] ?? 0) > 0,
    ),
  );

  function go(params: Record<string, string>) {
    const url = new URL(window.location.href);
    for (const [name, value] of Object.entries(params)) {
      if (value) {
        url.searchParams.set(name, value);
      } else {
        url.searchParams.delete(name);
      }
    }
    router.navigate(url);
  }

  function run_search(event: SubmitEvent) {
    event.preventDefault();
    go({ search: query.trim() });
  }
</script>

<div class="top">
  <div class="tabs" role="tablist">
    {#each tabs as [k, label] (k)}
      <button
        type="button"
        role="tab"
        aria-selected={kind === k}
        class:active={kind === k}
        onclick={() => {
          go({ kind: k });
        }}
      >
        {label}
        <span class="count">{result.counts[k || "all"] ?? 0}</span>
      </button>
    {/each}
  </div>
  <form class="search" onsubmit={run_search}>
    <Icon name="search" size={16} />
    <input
      type="search"
      placeholder="Search payee, category, amount…"
      bind:value={query}
    />
    {#if search}
      <button
        type="button"
        class="link"
        onclick={() => {
          go({ search: "" });
        }}>Clear</button
      >
    {/if}
  </form>
</div>

<p class="summary">
  <strong>{result.total}</strong>
  transaction{result.total === 1 ? "" : "s"}
  {#if sums.expense}· <strong>{money(sums.expense / 100, currency)}</strong>
    spent{/if}
  {#if sums.income}· <strong>{money(sums.income / 100, currency)}</strong>
    received{/if}
  {#if search}· matching “{search}”{/if}
  <span class="muted">· the Time filter in the header limits the dates</span>
</p>

{#if rows.length}
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Payee</th>
          <th>Category</th>
          <th>Paid with</th>
          <th class="num">Amount</th>
          <th class="icon-col"><span class="sr">Receipt</span></th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row (row.entry_hash)}
          <tr>
            <td class="date">{short_date(row.date)}</td>
            <td>
              <span class="badge {row.kind}">{kind_label(row.kind)}</span>
            </td>
            <td class="payee">
              <a href={`#context-${row.entry_hash}`} title="View or edit">
                <strong>{row.payee || row.narration}</strong>
                {#if row.payee && row.narration}
                  <span class="muted">{row.narration}</span>
                {/if}
              </a>
              {#if row.flag === "!"}
                <a class="review" href={$url_for("qb_review/")}>Needs review</a>
              {/if}
              {#each row.tags as tag (tag)}
                <span class="tag">#{tag}</span>
              {/each}
            </td>
            <td>
              {#each row.categories as c (c)}
                <span class="cell-line" title={c}>{leaf(c)}</span>
              {:else}
                <span class="muted">—</span>
              {/each}
            </td>
            <td>
              {#each row.paid_with as a (a)}
                <a
                  class="cell-line plain"
                  href={$url_for("qb_register/", { account_name: a })}
                  title="Open register for {a}">{leaf(a)}</a
                >
              {:else}
                <span class="muted">—</span>
              {/each}
            </td>
            <td class="num" class:income={row.kind === "income"}>
              {money(row.amount, row.currency)}
            </td>
            <td class="icon-col">
              {#each row.receipts as r (r.name)}
                {#if r.filename}
                  <a
                    class="clip"
                    href={$url_for_raw("document/", { filename: r.filename })}
                    target="_blank"
                    rel="noopener"
                    title="Receipt: {r.name}"
                  >
                    <Icon name="paperclip" size={16} />
                  </a>
                {:else}
                  <span
                    class="clip missing"
                    title="Receipt not found: {r.name}"
                  >
                    <Icon name="paperclip" size={16} />
                  </span>
                {/if}
              {/each}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if result.total > rows.length}
    <p class="muted">
      Showing the newest {rows.length}. Narrow the Time filter or search to see
      the rest.
    </p>
  {/if}
{:else}
  <p class="qb-card muted">No transactions match.</p>
{/if}

<p class="raw muted">
  Need every entry type (balances, notes, documents)? Use the
  <a href={$url_for("journal/")}>full journal</a>.
</p>

<style>
  .top {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
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
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
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
    width: min(22rem, 60vw);
    padding: 0.45em 0;
    outline: none;
    background: none;
    border: none;
  }

  .summary {
    margin: 0 0 0.8rem;
  }

  .muted {
    color: var(--qb-muted);
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
    padding: 0.55em 0.75em;
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

  .date,
  .num {
    white-space: nowrap;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .num.income {
    color: var(--qb-accent);
  }

  .badge {
    padding: 0.1em 0.55em;
    font-size: 0.8em;
    font-weight: 600;
    white-space: nowrap;
    background: var(--background-darker);
    border-radius: 999px;
  }

  .badge.expense {
    color: var(--error);
    background: color-mix(in srgb, var(--error) 10%, transparent);
  }

  .badge.income {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }

  .payee {
    min-width: 16rem;
    white-space: normal;
  }

  .payee a {
    color: inherit;
  }

  .payee strong {
    font-weight: 550;
  }

  .payee .muted {
    display: block;
    font-size: 0.9em;
  }

  .review,
  .tag {
    display: inline-block;
    margin: 0.2em 0.4em 0 0;
    font-size: 0.78em;
  }

  .payee a.review {
    padding: 0 0.5em;
    font-weight: 600;
    color: var(--warning);
    border: 1px solid currentcolor;
    border-radius: 999px;
  }

  .tag {
    color: var(--qb-muted);
  }

  .cell-line {
    display: block;
    white-space: nowrap;
  }

  .plain {
    color: inherit;
  }

  .icon-col {
    width: 2rem;
    text-align: center;
  }

  .clip {
    color: var(--qb-accent);
  }

  .clip.missing {
    color: var(--error);
  }

  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .link {
    padding: 0;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }

  .raw {
    margin-top: 1.2rem;
    font-size: 0.9em;
  }
</style>
