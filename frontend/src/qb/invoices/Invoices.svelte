<!--
  qb-fork: Invoices. Bookkeeping for invoices sent elsewhere: import or
  record them, see what's unpaid or overdue, and match payments.
-->
<script lang="ts">
  import { url_for, url_for_raw } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import type { QbInvoice } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import {
    days_between,
    in_tab,
    STATUS_TABS,
    status_label,
    summary,
  } from "./helpers.ts";
  import ImportInvoices from "./ImportInvoices.svelte";
  import type { InvoicesProps } from "./index.ts";
  import MatchPayment from "./MatchPayment.svelte";
  import RecordInvoice from "./RecordInvoice.svelte";

  let { data, tab, customer }: InvoicesProps = $props();

  let dialog = $state<"" | "import" | "record">("");
  let matching = $state<QbInvoice | null>(null);
  let query = $state("");

  let currency = $derived(data.invoices[0]?.currency ?? "USD");
  let mine = $derived(
    customer
      ? data.invoices.filter((i) => i.customer === customer)
      : data.invoices,
  );
  let totals = $derived(summary(mine, data.today));
  let counts = $derived(
    Object.fromEntries(
      STATUS_TABS.map(([t]) => [
        t,
        mine.filter((i) => in_tab(i.status, t)).length,
      ]),
    ),
  );
  let rows = $derived(
    mine.filter(
      (i) =>
        in_tab(i.status, tab) &&
        `${i.number} ${i.customer} ${i.memo}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
    ),
  );
  let customers = $derived([...new Set(data.invoices.map((i) => i.customer))]);

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

  function done() {
    dialog = "";
    matching = null;
    router.reload();
  }
</script>

<div class="page-head">
  <p class="muted">
    Keep track of invoices you send from Stripe, a PDF or another app. Import or
    record them here, then match each one to the deposit that paid it.
  </p>
  <div class="actions">
    <button
      type="button"
      class="qb-secondary"
      onclick={() => (dialog = "import")}
    >
      <Icon name="upload" size={16} /> Import invoices
    </button>
    <button
      type="button"
      class="qb-primary"
      onclick={() => (dialog = "record")}
    >
      <Icon name="plus" size={16} /> Record an invoice
    </button>
  </div>
</div>

<div class="money-bar">
  <button
    type="button"
    class="seg overdue"
    onclick={() => {
      go({ status: "overdue" });
    }}
  >
    <span>Overdue</span>
    <strong>{money(totals.overdue / 100, currency)}</strong>
  </button>
  <button
    type="button"
    class="seg due"
    onclick={() => {
      go({ status: "unpaid" });
    }}
  >
    <span>Not due yet</span>
    <strong>{money(totals.not_due / 100, currency)}</strong>
  </button>
  <button
    type="button"
    class="seg paid"
    onclick={() => {
      go({ status: "paid" });
    }}
  >
    <span>Paid, last 30 days</span>
    <strong>{money(totals.paid_30 / 100, currency)}</strong>
  </button>
</div>

<div class="toolbar">
  <div class="tabs" role="tablist">
    {#each STATUS_TABS as [t, label] (t)}
      <button
        type="button"
        role="tab"
        aria-selected={tab === t}
        class:active={tab === t}
        onclick={() => {
          go({ status: t });
        }}
      >
        {label} <span class="count">{counts[t]}</span>
      </button>
    {/each}
    {#if customer}
      <span class="filter-chip">
        Customer: {customer}
        <button
          type="button"
          aria-label="Show all customers"
          onclick={() => {
            go({ customer: "" });
          }}><Icon name="x" size={14} /></button
        >
      </span>
    {/if}
  </div>
  <label class="search">
    <Icon name="search" size={16} />
    <input
      type="search"
      placeholder="Search number, customer…"
      bind:value={query}
    />
  </label>
</div>

{#if rows.length}
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>No.</th>
          <th>Customer</th>
          <th>Due</th>
          <th class="num">Total</th>
          <th class="num">Balance</th>
          <th>Status</th>
          <th class="icon-col"><span class="sr">Invoice file</span></th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each rows as inv (inv.number)}
          <tr>
            <td class="nowrap">{short_date(inv.date)}</td>
            <td class="nowrap">
              <a
                href={`#context-${inv.entry_hashes[0] ?? ""}`}
                title="View or edit">{inv.number}</a
              >
            </td>
            <td>
              <a
                class="plain"
                href={$url_for("qb_invoices/", { customer: inv.customer })}
                >{inv.customer}</a
              >
              {#if inv.memo && !inv.memo.endsWith(inv.number)}
                <span class="muted sub">{inv.memo}</span>
              {/if}
            </td>
            <td class="nowrap">
              {#if inv.due}
                {short_date(inv.due)}
                {#if inv.status === "overdue"}
                  <span class="late"
                    >{days_between(inv.due, data.today)} days late</span
                  >
                {/if}
              {:else}
                <span class="muted">—</span>
              {/if}
            </td>
            <td class="num">{money(inv.amount, inv.currency)}</td>
            <td class="num">{money(inv.balance, inv.currency)}</td>
            <td>
              <span class="status {inv.status}">{status_label(inv.status)}</span
              >
              {#if inv.source === "stripe"}<span class="muted sub"
                  >via Stripe</span
                >{/if}
            </td>
            <td class="icon-col">
              {#each inv.receipts as r (r.name)}
                {#if r.filename}
                  <a
                    class="clip"
                    href={$url_for_raw("document/", { filename: r.filename })}
                    target="_blank"
                    rel="noopener"
                    title={r.name}><Icon name="paperclip" size={16} /></a
                  >
                {/if}
              {/each}
            </td>
            <td class="nowrap">
              {#if inv.status !== "paid"}
                <button
                  type="button"
                  class="qb-secondary small"
                  onclick={() => (matching = inv)}>Match payment</button
                >
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{:else if data.invoices.length}
  <p class="qb-card muted">No invoices here.</p>
{:else}
  <div class="qb-card empty">
    <span class="big-icon"><Icon name="receipt" size={28} /></span>
    <h2>No invoices yet</h2>
    <p class="muted">
      Invoices paid through Stripe show up here on their own once you import
      Stripe payouts (with the invoice_id column). For anything else, import
      your invoice list as a CSV or record one invoice at a time.
    </p>
    <div class="actions">
      <button
        type="button"
        class="qb-secondary"
        onclick={() => (dialog = "import")}>Import invoices</button
      >
      <button
        type="button"
        class="qb-primary"
        onclick={() => (dialog = "record")}>Record an invoice</button
      >
    </div>
  </div>
{/if}

<p class="hint muted">
  Invoices show for all dates; the Time filter doesn't apply here. Recorded and
  imported invoices count as income on their invoice date.
</p>

{#if dialog === "import"}
  <ImportInvoices
    income_accounts={data.income_accounts}
    ar_account={data.ar_account}
    onclose={() => (dialog = "")}
    ondone={done}
  />
{:else if dialog === "record"}
  <RecordInvoice
    {customers}
    income_accounts={data.income_accounts}
    ar_account={data.ar_account}
    onclose={() => (dialog = "")}
    ondone={done}
  />
{/if}
{#if matching}
  <MatchPayment
    invoice={matching}
    onclose={() => (matching = null)}
    ondone={done}
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

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .actions button {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
  }

  .muted {
    color: var(--qb-muted);
  }

  .money-bar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr));
    gap: 0.6rem;
    margin-bottom: 1rem;
  }

  .seg {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 0.7rem 1rem;
    color: var(--text-color);
    text-align: left;
    background: var(--qb-surface);
    border: 1px solid var(--border);
    border-bottom-width: 5px;
    border-radius: 10px;
  }

  .seg span {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .seg strong {
    font-size: 1.35rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .seg.overdue {
    border-bottom-color: var(--error);
  }

  .seg.due {
    border-bottom-color: var(--warning);
  }

  .seg.paid {
    border-bottom-color: var(--qb-accent);
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
    align-items: center;
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

  .filter-chip {
    display: inline-flex;
    gap: 0.3rem;
    align-items: center;
    padding: 0.25em 0.4em 0.25em 0.8em;
    font-size: 0.9em;
    background: var(--background-darker);
    border-radius: 999px;
  }

  .filter-chip button {
    display: grid;
    place-items: center;
    padding: 0.1em;
    color: inherit;
    background: none;
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
    width: min(18rem, 60vw);
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

  .nowrap,
  .num {
    white-space: nowrap;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .plain {
    color: inherit;
  }

  .sub {
    display: block;
    font-size: 0.85em;
  }

  .late {
    display: block;
    font-size: 0.8em;
    font-weight: 600;
    color: var(--error);
  }

  .status {
    padding: 0.1em 0.6em;
    font-size: 0.8em;
    font-weight: 600;
    white-space: nowrap;
    background: var(--background-darker);
    border-radius: 999px;
  }

  .status.paid {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }

  .status.overdue {
    color: var(--error);
    background: color-mix(in srgb, var(--error) 10%, transparent);
  }

  .status.partial,
  .status.open {
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 12%, transparent);
  }

  .icon-col {
    width: 2rem;
    text-align: center;
  }

  .clip {
    color: var(--qb-accent);
  }

  .small {
    padding: 0.3em 0.9em;
    font-size: 0.85em;
  }

  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .empty {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    align-items: center;
    padding: 2.5rem 1rem;
    text-align: center;
  }

  .empty h2 {
    margin: 0;
    font-size: 1.15rem;
  }

  .empty p {
    max-width: 36rem;
  }

  .big-icon {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  .hint {
    margin-top: 1rem;
    font-size: 0.88em;
  }
</style>
