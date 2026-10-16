<!--
  qb-fork: Customers or Vendors. Everyone you've sold to or paid, from
  invoices and bills and from income and expense transactions.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import type { QbParty } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import { leaf } from "../transactions/helpers.ts";
  import type { SideText } from "./sides.ts";

  let { text, parties }: { text: SideText; parties: QbParty[] } = $props();

  let query = $state("");
  let only_owing = $state(false);

  let currency = $derived(parties[0]?.currency ?? "USD");
  const cents = (list: QbParty[], pick: (p: QbParty) => number) =>
    list.reduce((sum, p) => sum + Math.round(pick(p) * 100), 0) / 100;
  let open_total = $derived(cents(parties, (p) => p.open_balance));
  let overdue_total = $derived(cents(parties, (p) => p.overdue));
  let total = $derived(cents(parties, (p) => p.total));
  let rows = $derived(
    parties.filter(
      (p) =>
        (!only_owing || p.open_balance > 0) &&
        `${p.name} ${p.email} ${p.category}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
    ),
  );
  let docs_url = $derived(`${text.docs_report}/` as const);
</script>

<p class="intro muted">{text.parties_intro}</p>

<div class="cards">
  <div class="qb-card stat">
    <span>{text.parties_title}</span>
    <strong>{parties.length}</strong>
  </div>
  <div class="qb-card stat">
    <span>{text.total_label}</span>
    <strong>{money(total, currency)}</strong>
  </div>
  <a class="qb-card stat" href={$url_for(docs_url, { status: "unpaid" })}>
    <span>Open balance</span>
    <strong>{money(open_total, currency)}</strong>
  </a>
  <a class="qb-card stat" href={$url_for(docs_url, { status: "overdue" })}>
    <span>Overdue</span>
    <strong class:negative={overdue_total > 0}
      >{money(overdue_total, currency)}</strong
    >
  </a>
</div>

{#if parties.length}
  <div class="toolbar">
    <label class="search">
      <Icon name="search" size={16} />
      <input
        type="search"
        placeholder="Search {text.parties_title.toLowerCase()}…"
        bind:value={query}
      />
    </label>
    <label class="owing">
      <input type="checkbox" bind:checked={only_owing} />
      {text.owing_label}
    </label>
  </div>

  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th>{text.party_title}</th>
          <th>Usual category</th>
          <th class="num">{text.docs_title}</th>
          <th class="num">{text.side === "invoice" ? "Sales" : "Spent"}</th>
          <th class="num">Open balance</th>
          <th class="num">Overdue</th>
          <th>Last activity</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as p (p.name)}
          <tr>
            <td>
              <a class="cust-link" href={$url_for(docs_url, { party: p.name })}
                ><strong class="cust-name">{p.name}</strong></a
              >
              {#if p.email}<span class="muted sub">{p.email}</span>{/if}
            </td>
            <td class="muted" title={p.category}>{leaf(p.category)}</td>
            <td class="num">{p.docs || "—"}</td>
            <td class="num">{money(p.total, p.currency)}</td>
            <td class="num">
              {p.open_balance ? money(p.open_balance, p.currency) : "—"}
            </td>
            <td class="num" class:negative={p.overdue > 0}>
              {p.overdue ? money(p.overdue, p.currency) : "—"}
            </td>
            <td class="nowrap">{short_date(p.last_date)}</td>
          </tr>
        {:else}
          <tr
            ><td colspan="7" class="muted"
              >No {text.parties_title.toLowerCase()} match.</td
            ></tr
          >
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <div class="qb-card empty">
    <span class="big-icon"><Icon name="users" size={28} /></span>
    <h2>No {text.parties_title.toLowerCase()} yet</h2>
    <p class="muted">{text.parties_empty}</p>
    <a class="button qb-primary" href={$url_for(docs_url)}
      >Go to {text.docs_title}</a
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
