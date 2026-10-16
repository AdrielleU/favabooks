<!--
  qb-fork: Customers. Everyone who has paid you or owes you, from invoices
  and income transactions (`customer:` metadata, or the payee).
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import type { QbCustomer } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";

  let { customers }: { customers: QbCustomer[] } = $props();

  let query = $state("");
  let only_owing = $state(false);

  let currency = $derived(customers[0]?.currency ?? "USD");
  const cents = (list: QbCustomer[], pick: (c: QbCustomer) => number) =>
    list.reduce((sum, c) => sum + Math.round(pick(c) * 100), 0) / 100;
  let open_total = $derived(cents(customers, (c) => c.open_balance));
  let overdue_total = $derived(cents(customers, (c) => c.overdue));
  let sales_total = $derived(cents(customers, (c) => c.sales));
  let rows = $derived(
    customers.filter(
      (c) =>
        (!only_owing || c.open_balance > 0) &&
        `${c.name} ${c.email}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
    ),
  );
</script>

<p class="intro muted">
  Customers come from your invoices and income: the <code>customer</code> on Stripe
  sales and recorded invoices, or the payee of a deposit filed as income.
</p>

<div class="cards">
  <div class="qb-card stat">
    <span>Customers</span>
    <strong>{customers.length}</strong>
  </div>
  <div class="qb-card stat">
    <span>Total sales</span>
    <strong>{money(sales_total, currency)}</strong>
  </div>
  <a class="qb-card stat" href={$url_for("qb_invoices/", { status: "unpaid" })}>
    <span>Open balance</span>
    <strong>{money(open_total, currency)}</strong>
  </a>
  <a
    class="qb-card stat"
    href={$url_for("qb_invoices/", { status: "overdue" })}
  >
    <span>Overdue</span>
    <strong class:negative={overdue_total > 0}
      >{money(overdue_total, currency)}</strong
    >
  </a>
</div>

{#if customers.length}
  <div class="toolbar">
    <label class="search">
      <Icon name="search" size={16} />
      <input type="search" placeholder="Search customers…" bind:value={query} />
    </label>
    <label class="owing">
      <input type="checkbox" bind:checked={only_owing} /> Only customers who owe you
    </label>
  </div>

  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th>Customer</th>
          <th class="num">Invoices</th>
          <th class="num">Sales</th>
          <th class="num">Open balance</th>
          <th class="num">Overdue</th>
          <th>Last activity</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as c (c.name)}
          <tr>
            <td>
              <a
                class="cust-link"
                href={$url_for("qb_invoices/", { customer: c.name })}
                ><strong class="cust-name">{c.name}</strong></a
              >
              {#if c.email}<span class="muted sub">{c.email}</span>{/if}
            </td>
            <td class="num">{c.invoices || "—"}</td>
            <td class="num">{money(c.sales, c.currency)}</td>
            <td class="num">
              {c.open_balance ? money(c.open_balance, c.currency) : "—"}
            </td>
            <td class="num" class:negative={c.overdue > 0}>
              {c.overdue ? money(c.overdue, c.currency) : "—"}
            </td>
            <td class="nowrap">{short_date(c.last_date)}</td>
          </tr>
        {:else}
          <tr><td colspan="6" class="muted">No customers match.</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <div class="qb-card empty">
    <span class="big-icon"><Icon name="users" size={28} /></span>
    <h2>No customers yet</h2>
    <p class="muted">
      Customers appear when you import Stripe payouts, import or record
      invoices, or file a deposit as income.
    </p>
    <a class="button qb-primary" href={$url_for("qb_invoices/")}
      >Go to Invoices</a
    >
  </div>
{/if}

<style>
  .intro {
    max-width: 50rem;
    margin: 0 0 1rem;
  }

  .muted {
    color: var(--qb-muted);
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
    color: inherit;
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

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1.2rem;
    align-items: center;
    margin-bottom: 0.6rem;
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

  .owing {
    display: flex;
    gap: 0.4rem;
    align-items: center;
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

  .cust-link {
    color: inherit;
  }

  .cust-name {
    font-weight: 550;
  }

  .sub {
    display: block;
    font-size: 0.85em;
  }

  .num,
  .nowrap {
    white-space: nowrap;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .negative {
    color: var(--error);
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

  .big-icon {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  a.button {
    color: var(--button-color);
    background: var(--button-background);
  }
</style>
