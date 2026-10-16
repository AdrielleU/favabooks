<!--
  qb-fork: All transactions. Every transaction in the header filters, newest
  first, with its type, category, the account it was paid with, the amount,
  and its receipt.
-->
<script lang="ts">
  import { url_for, url_for_raw } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import type { QbTransactionRow } from "../api.ts";
  import PeriodPicker from "../docs/PeriodPicker.svelte";
  import { iso, sort_by, to_csv } from "../docs/periods.ts";
  import SortHeader from "../docs/SortHeader.svelte";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import { KIND_TABS, kind_label, leaf, totals } from "./helpers.ts";
  import type { TransactionsProps } from "./index.ts";

  let { search, kind, result, today, period }: TransactionsProps = $props();

  type SortKey = "date" | "type" | "payee" | "category" | "paid" | "amount";
  let sort_key = $state<SortKey>("date");
  let descending = $state(true);
  const SORT: Record<SortKey, (r: QbTransactionRow) => string | number | Date> =
    {
      date: (r) => r.date,
      type: (r) => r.kind,
      payee: (r) => (r.payee || r.narration).toLowerCase(),
      category: (r) => r.categories.join(" ").toLowerCase(),
      paid: (r) => r.paid_with.join(" ").toLowerCase(),
      amount: (r) => r.amount,
    };
  function sort(key: SortKey) {
    descending =
      sort_key === key ? !descending : key === "date" || key === "amount";
    sort_key = key;
  }

  let query = $derived(search);
  let rows = $derived(sort_by(result.rows, SORT[sort_key], descending));
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

  function export_csv() {
    const csv = to_csv([
      [
        "Date",
        "Type",
        "Payee",
        "Description",
        "Category",
        "Paid with",
        "Amount",
        "Currency",
        "Needs review",
        "Receipt",
      ],
      ...rows.map((r) => [
        iso(r.date),
        kind_label(r.kind),
        r.payee,
        r.narration,
        r.categories.join(" "),
        r.paid_with.join(" "),
        r.amount.toFixed(2),
        r.currency,
        r.flag === "!" ? "yes" : "",
        r.receipts.map((x) => x.name).join(" "),
      ]),
    ]);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = `transactions-${period.key}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function run_search(event: SubmitEvent) {
    event.preventDefault();
    go({ search: query.trim() });
  }
</script>

<div class="cards">
  <div class="qb-card stat">
    <span>Transactions</span>
    <strong>{result.counts.all ?? 0}</strong>
  </div>
  <div class="qb-card stat">
    <span>Money out (expenses)</span>
    <strong>{money(sums.expense / 100, currency)}</strong>
  </div>
  <div class="qb-card stat">
    <span>Money in (income)</span>
    <strong class="in">{money(sums.income / 100, currency)}</strong>
  </div>
  <button
    type="button"
    class="qb-card stat review-card"
    onclick={() => {
      go({ kind: "review" });
    }}
  >
    <span>Needs review</span>
    <strong class:warn={(result.counts.review ?? 0) > 0}
      >{result.counts.review ?? 0}</strong
    >
  </button>
</div>

<div class="period-row">
  <PeriodPicker {period} {today} dates={result.months} />
  {#if period.key !== "all"}<span class="muted">{period.label}</span>{/if}
</div>

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

{#if search}
  <p class="summary">
    {result.total} matching “{search}”
  </p>
{/if}

{#if rows.length}
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          {#each [["date", "Date"], ["type", "Type"], ["payee", "Payee"], ["category", "Category"], ["paid", "Paid with"], ["amount", "Amount"]] as const as [key, label] (key)}
            <SortHeader
              {label}
              active={sort_key === key}
              {descending}
              num={key === "amount"}
              onsort={() => {
                sort(key);
              }}
            />
          {/each}
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
      <tfoot>
        <tr>
          <td colspan="5">
            {rows.length} transaction{rows.length === 1 ? "" : "s"}
            {#if sums.expense && sums.income}
              <span class="muted"
                >· net {money(
                  (sums.income - sums.expense) / 100,
                  currency,
                )}</span
              >
            {/if}
          </td>
          <td class="num">
            {#if sums.expense}<span class="foot-line"
                >{money(sums.expense / 100, currency)} out</span
              >{/if}
            {#if sums.income}<span class="foot-line in"
                >{money(sums.income / 100, currency)} in</span
              >{/if}
          </td>
          <td></td>
        </tr>
      </tfoot>
    </table>
  </div>
  <div class="below">
    <button type="button" class="qb-secondary small" onclick={export_csv}>
      <Icon name="download" size={15} /> Export CSV
    </button>
  </div>
  {#if result.total > rows.length}
    <p class="muted">
      Showing the newest {rows.length}. Narrow the dates or search to see the
      rest.
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

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
    gap: 0.8rem;
    margin-bottom: 1rem;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    align-items: flex-start;
    color: inherit;
    text-align: left;
  }

  .stat span {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .stat strong {
    font-size: 1.4rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .review-card {
    font: inherit;
    cursor: pointer;
  }

  .stat .warn {
    color: var(--warning);
  }

  .period-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    margin-bottom: 0.7rem;
  }

  .foot-line {
    display: block;
  }

  .in {
    color: var(--qb-accent);
  }

  .below {
    display: flex;
    justify-content: flex-end;
    margin-top: 0.6rem;
  }

  .small {
    padding: 0.3em 0.9em;
    font-size: 0.88em;
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

  tfoot td {
    font-weight: 600;
    border-bottom: none;
  }
</style>
