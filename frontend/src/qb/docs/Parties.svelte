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
  import PeriodPicker from "./PeriodPicker.svelte";
  import type { Period } from "./periods.ts";
  import { iso, nec_threshold, sort_by, to_csv } from "./periods.ts";
  import SortHeader from "./SortHeader.svelte";
  import type { SideText } from "./sides.ts";

  let {
    text,
    parties,
    today,
    period,
    dates,
  }: {
    text: SideText;
    parties: QbParty[];
    today: Date;
    period: Period;
    dates: Date[];
  } = $props();

  /** The 1099-NEC threshold for the period's year. */
  let threshold = $derived(nec_threshold(period, today));
  let is_vendor = $derived(text.side === "bill");

  type SortKey =
    "name" | "docs" | "total" | "open" | "overdue" | "bank" | "last";
  let sort_key = $state<SortKey>("total");
  let descending = $state(true);
  const SORT: Record<SortKey, (p: QbParty) => string | number | Date> = {
    name: (p) => p.name.toLowerCase(),
    docs: (p) => p.docs,
    total: (p) => p.total,
    open: (p) => p.open_balance,
    overdue: (p) => p.overdue,
    bank: (p) => p.bank_paid,
    last: (p) => p.last_date,
  };
  function sort(key: SortKey) {
    descending = sort_key === key ? !descending : key !== "name";
    sort_key = key;
  }

  let query = $state("");
  let only_owing = $state(false);

  let currency = $derived(parties[0]?.currency ?? "USD");
  const cents = (list: QbParty[], pick: (p: QbParty) => number) =>
    list.reduce((sum, p) => sum + Math.round(pick(p) * 100), 0) / 100;
  let open_total = $derived(cents(parties, (p) => p.open_balance));
  let overdue_total = $derived(cents(parties, (p) => p.overdue));
  let total = $derived(cents(parties, (p) => p.total));
  let rows = $derived(
    sort_by(
      parties.filter(
        (p) =>
          (!only_owing || p.open_balance > 0) &&
          `${p.name} ${p.email} ${p.category}`
            .toLowerCase()
            .includes(query.trim().toLowerCase()),
      ),
      SORT[sort_key],
      descending,
    ),
  );

  function export_csv() {
    const csv = to_csv([
      [
        text.party_title,
        "Email",
        "Usual category",
        text.docs_title,
        text.total_label,
        "Open balance",
        "Overdue",
        ...(is_vendor ? ["Paid by bank or check"] : []),
        "Last activity",
      ],
      ...rows.map((p) => [
        p.name,
        p.email,
        p.category,
        p.docs,
        p.total.toFixed(2),
        p.open_balance.toFixed(2),
        p.overdue.toFixed(2),
        ...(is_vendor ? [p.bank_paid.toFixed(2)] : []),
        iso(p.last_date),
      ]),
    ]);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = `${text.parties_title.toLowerCase()}-${period.key}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }
  let docs_url = $derived(`${text.docs_report}/` as const);
</script>

<div class="head">
  <p class="intro muted">{text.parties_intro}</p>
  <PeriodPicker {period} {today} {dates} />
</div>

<div class="cards">
  <div class="qb-card stat">
    <span>{text.parties_title}</span>
    <strong>{parties.length}</strong>
  </div>
  <div class="qb-card stat">
    <span
      >{text.total_label}{period.key === "all" ? "" : `, ${period.label}`}</span
    >
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
          <SortHeader
            label={text.party_title}
            active={sort_key === "name"}
            {descending}
            onsort={() => {
              sort("name");
            }}
          />
          <th>Usual category</th>
          <SortHeader
            label={text.docs_title}
            active={sort_key === "docs"}
            {descending}
            num
            onsort={() => {
              sort("docs");
            }}
          />
          <SortHeader
            label={text.side === "invoice" ? "Sales" : "Spent"}
            active={sort_key === "total"}
            {descending}
            num
            onsort={() => {
              sort("total");
            }}
          />
          <SortHeader
            label="Open balance"
            active={sort_key === "open"}
            {descending}
            num
            onsort={() => {
              sort("open");
            }}
          />
          <SortHeader
            label="Overdue"
            active={sort_key === "overdue"}
            {descending}
            num
            onsort={() => {
              sort("overdue");
            }}
          />
          {#if is_vendor}<SortHeader
              label="Bank / check"
              active={sort_key === "bank"}
              {descending}
              num
              onsort={() => {
                sort("bank");
              }}
            />{/if}
          <SortHeader
            label="Last activity"
            active={sort_key === "last"}
            {descending}
            onsort={() => {
              sort("last");
            }}
          />
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
            {#if is_vendor}
              <td class="num">
                {p.bank_paid ? money(p.bank_paid, p.currency) : "—"}
                {#if p.bank_paid >= threshold}
                  <span
                    class="nec"
                    title="Paid {money(
                      p.bank_paid,
                      p.currency,
                    )} by bank or check: check whether this vendor needs a 1099-NEC (ask for a W-9)."
                    >1099?</span
                  >
                {/if}
              </td>
            {/if}
            <td class="nowrap">{short_date(p.last_date)}</td>
          </tr>
        {:else}
          <tr
            ><td colspan="8" class="muted"
              >No {text.parties_title.toLowerCase()} match.</td
            ></tr
          >
        {/each}
      </tbody>
    </table>
  </div>
  <div class="below">
    {#if is_vendor}
      <p class="muted small-note">
        Bank / check is what you paid each vendor from bank or cash accounts in
        the period. Those payments count toward a 1099-NEC (flagged from
        {money(threshold, currency)} for this period's year); card and PayPal payments
        don't, they're reported on a 1099-K. Pick a year above to review a tax year,
        and confirm with your CPA.
      </p>
    {/if}
    <button type="button" class="qb-secondary small" onclick={export_csv}>
      <Icon name="download" size={15} /> Export CSV
    </button>
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
  .head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .intro {
    max-width: 50rem;
    margin: 0;
  }

  .nec {
    display: inline-block;
    padding: 0 0.4em;
    margin-left: 0.3em;
    font-size: 0.75em;
    font-weight: 700;
    color: var(--warning);
    border: 1px solid currentcolor;
    border-radius: 999px;
  }

  .below {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1rem;
    align-items: flex-start;
    justify-content: space-between;
    margin-top: 0.6rem;
  }

  .small-note {
    max-width: 46rem;
    margin: 0;
    font-size: 0.85em;
  }

  .small {
    padding: 0.3em 0.9em;
    font-size: 0.88em;
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
