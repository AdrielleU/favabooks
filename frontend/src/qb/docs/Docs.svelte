<!--
  qb-fork: Invoices or Bills. Bookkeeping for documents sent or received
  elsewhere: import or record them, see what's unpaid or overdue, and match
  payments.
-->
<script lang="ts">
  import { url_for, url_for_raw } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import type { QbDoc, QbDocs } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import { leaf } from "../transactions/helpers.ts";
  import {
    days_between,
    in_tab,
    STATUS_TABS,
    status_label,
    summary,
  } from "./helpers.ts";
  import ImportDocs from "./ImportDocs.svelte";
  import MatchPayment from "./MatchPayment.svelte";
  import PeriodPicker from "./PeriodPicker.svelte";
  import type { Period } from "./periods.ts";
  import {
    AGING_BUCKETS,
    aging,
    in_period,
    iso,
    sort_by,
    to_csv,
  } from "./periods.ts";
  import RecordDoc from "./RecordDoc.svelte";
  import SortHeader from "./SortHeader.svelte";
  import type { SideText } from "./sides.ts";

  let {
    text,
    data,
    tab,
    party,
    today,
    period,
  }: {
    text: SideText;
    data: QbDocs;
    today: Date;
    period: Period;
    /** Status tab ("", unpaid, overdue, paid). */
    tab: string;
    /** Only this customer's or vendor's documents ("" for all). */
    party: string;
  } = $props();

  let dialog = $state<"" | "import" | "record">("");
  let matching = $state<QbDoc | null>(null);
  let query = $state("");

  let currency = $derived(data.docs[0]?.currency ?? "USD");
  let mine = $derived(
    data.docs.filter(
      (d) => (!party || d.party === party) && in_period(d.date, period),
    ),
  );
  let buckets = $derived(aging(mine, data.today));
  let has_unpaid = $derived(buckets.some((b) => b > 0));
  let totals = $derived(summary(mine, data.today));
  let counts = $derived(
    Object.fromEntries(
      STATUS_TABS.map(([t]) => [
        t,
        mine.filter((d) => in_tab(d.status, t)).length,
      ]),
    ),
  );
  type SortKey = "date" | "number" | "party" | "due" | "amount" | "balance";
  let sort_key = $state<SortKey>("date");
  let descending = $state(true);
  const SORT: Record<SortKey, (d: QbDoc) => string | number | Date | null> = {
    date: (d) => d.date,
    number: (d) => d.number,
    party: (d) => d.party.toLowerCase(),
    due: (d) => d.due,
    amount: (d) => d.amount,
    balance: (d) => d.balance,
  };
  function sort(key: SortKey) {
    descending = sort_key === key ? !descending : key !== "party";
    sort_key = key;
  }
  let rows = $derived(
    sort_by(
      mine.filter(
        (d) =>
          in_tab(d.status, tab) &&
          `${d.number} ${d.party} ${d.memo} ${d.categories.join(" ")}`
            .toLowerCase()
            .includes(query.trim().toLowerCase()),
      ),
      SORT[sort_key],
      descending,
    ),
  );
  const cents_sum = (list: QbDoc[], pick: (d: QbDoc) => number) =>
    list.reduce((sum, d) => sum + Math.round(pick(d) * 100), 0) / 100;
  let party_docs = $derived(
    party ? data.docs.filter((d) => d.party === party) : [],
  );

  function export_csv() {
    const csv = to_csv([
      [
        "Date",
        "Number",
        text.party_title,
        "Category",
        "Due",
        "Total",
        "Paid",
        "Balance",
        "Status",
        "Paid on",
        "Currency",
      ],
      ...rows.map((d) => [
        iso(d.date),
        d.number,
        d.party,
        d.categories.join(" "),
        d.due ? iso(d.due) : "",
        d.amount.toFixed(2),
        d.paid.toFixed(2),
        d.balance.toFixed(2),
        status_label(d.status),
        d.paid_date ? iso(d.paid_date) : "",
        d.currency,
      ]),
    ]);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = `${text.docs_title.toLowerCase()}-${period.key}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }
  let parties = $derived([...new Set(data.docs.map((d) => d.party))]);
  let a_doc = $derived(text.side === "invoice" ? "an invoice" : "a bill");
  let is_bill = $derived(text.side === "bill");
  /** "Liabilities:CreditCard:Card-8360" -> "Card-8360". */
  const last = (account: string) => account.split(":").pop() ?? account;

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
  <p class="muted">{text.docs_intro}</p>
  <div class="actions">
    <button
      type="button"
      class="qb-secondary"
      onclick={() => (dialog = "import")}
    >
      <Icon name="upload" size={16} /> Import {text.docs_title.toLowerCase()}
    </button>
    <button
      type="button"
      class="qb-primary"
      onclick={() => (dialog = "record")}
    >
      <Icon name="plus" size={16} /> Record {a_doc}
    </button>
  </div>
</div>

{#if party}
  <div class="qb-card party-head">
    <div>
      <span class="muted">{text.party_title}</span>
      <h2>{party}</h2>
    </div>
    <div class="stat">
      <span>{text.docs_title}</span>
      <strong>{party_docs.length}</strong>
    </div>
    <div class="stat">
      <span>{text.total_label}</span>
      <strong
        >{money(
          cents_sum(party_docs, (d) => d.amount),
          currency,
        )}</strong
      >
    </div>
    <div class="stat">
      <span>Open balance</span>
      <strong
        >{money(
          cents_sum(party_docs, (d) => d.balance),
          currency,
        )}</strong
      >
    </div>
    <a href={$url_for(`${text.parties_report}/`)} class="back"
      >All {text.parties_title.toLowerCase()}</a
    >
  </div>
{/if}

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
    <span>{text.paid_label}</span>
    <strong>{money(totals.paid_30 / 100, currency)}</strong>
  </button>
</div>

{#if has_unpaid}
  <div class="aging" aria-label="Unpaid by days past due">
    {#each AGING_BUCKETS as label, i (label)}
      <div class="bucket" class:late={i > 0 && (buckets[i] ?? 0) > 0}>
        <span class="bucket-label">{label}</span>
        <strong class="bucket-value"
          >{money((buckets[i] ?? 0) / 100, currency)}</strong
        >
      </div>
    {/each}
  </div>
{/if}

<div class="toolbar">
  <PeriodPicker {period} {today} dates={data.docs.map((d) => d.date)} />
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
    {#if party}
      <span class="filter-chip">
        {text.party_title}: {party}
        <button
          type="button"
          aria-label="Show all {text.parties_title.toLowerCase()}"
          onclick={() => {
            go({ party: "" });
          }}><Icon name="x" size={14} /></button
        >
      </span>
    {/if}
  </div>
  <label class="search">
    <Icon name="search" size={16} />
    <input
      type="search"
      placeholder="Search number, {text.party}…"
      bind:value={query}
    />
  </label>
</div>

{#if rows.length}
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <SortHeader
            label="Date"
            active={sort_key === "date"}
            {descending}
            onsort={() => {
              sort("date");
            }}
          />
          <SortHeader
            label="No."
            active={sort_key === "number"}
            {descending}
            onsort={() => {
              sort("number");
            }}
          />
          <SortHeader
            label={text.party_title}
            active={sort_key === "party"}
            {descending}
            onsort={() => {
              sort("party");
            }}
          />
          {#if is_bill}<th>Category</th>{/if}
          <SortHeader
            label="Due"
            active={sort_key === "due"}
            {descending}
            onsort={() => {
              sort("due");
            }}
          />
          <SortHeader
            label="Total"
            active={sort_key === "amount"}
            {descending}
            num
            onsort={() => {
              sort("amount");
            }}
          />
          <SortHeader
            label="Balance"
            active={sort_key === "balance"}
            {descending}
            num
            onsort={() => {
              sort("balance");
            }}
          />
          <th>Status</th>
          <th class="icon-col"><span class="sr">File</span></th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each rows as d (d.key)}
          <tr>
            <td class="nowrap">{short_date(d.date)}</td>
            <td class="doc-no">
              <a
                href={`#context-${d.entry_hashes[0] ?? ""}`}
                title="View or edit">{d.number}</a
              >
            </td>
            <td class="party-cell">
              <a
                class="plain"
                href={$url_for(`${text.docs_report}/`, { party: d.party })}
                >{d.party}</a
              >
              {#if d.memo && !d.memo.endsWith(d.number)}
                <span class="muted sub">{d.memo}</span>
              {/if}
            </td>
            {#if is_bill}
              <td>
                {#each d.categories as c (c)}
                  <span class="cell-line" title={c}>{leaf(c)}</span>
                {/each}
              </td>
            {/if}
            <td class="nowrap">
              {#if d.due}
                {short_date(d.due)}
                {#if d.status === "overdue"}
                  <span class="late"
                    >{days_between(d.due, data.today)} days late</span
                  >
                {/if}
              {:else}
                <span class="muted">—</span>
              {/if}
            </td>
            <td class="num">{money(d.amount, d.currency)}</td>
            <td class="num">{money(d.balance, d.currency)}</td>
            <td>
              <span class="status {d.status}">{status_label(d.status)}</span>
              {#if d.paid_date && d.status === "paid"}
                <span class="muted sub paid-with" title={d.paid_with.join(", ")}
                  >{short_date(d.paid_date)}{d.paid_with.length
                    ? ` ${text.paid_with_label} ${d.paid_with.map(last).join(", ")}`
                    : ""}</span
                >
              {/if}
            </td>
            <td class="icon-col">
              {#each d.receipts as r (r.name)}
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
              {#if d.status !== "paid"}
                <button
                  type="button"
                  class="qb-secondary small"
                  onclick={() => (matching = d)}>Match payment</button
                >
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <td colspan={is_bill ? 5 : 4}>
            {rows.length}
            {rows.length === 1 ? text.doc : `${text.doc}s`}
          </td>
          <td class="num"
            >{money(
              cents_sum(rows, (d) => d.amount),
              currency,
            )}</td
          >
          <td class="num"
            >{money(
              cents_sum(rows, (d) => d.balance),
              currency,
            )}</td
          >
          <td colspan="3"></td>
        </tr>
      </tfoot>
    </table>
  </div>
  <div class="below">
    <button type="button" class="qb-secondary small" onclick={export_csv}>
      <Icon name="download" size={15} /> Export CSV
    </button>
  </div>
{:else if data.docs.length}
  <p class="qb-card muted">No {text.docs_title.toLowerCase()} here.</p>
{:else}
  <div class="qb-card empty">
    <span class="big-icon"><Icon name="receipt" size={28} /></span>
    <h2>No {text.docs_title.toLowerCase()} yet</h2>
    <p class="muted">{text.docs_empty}</p>
    <div class="actions">
      <button
        type="button"
        class="qb-secondary"
        onclick={() => (dialog = "import")}
        >Import {text.docs_title.toLowerCase()}</button
      >
      <button
        type="button"
        class="qb-primary"
        onclick={() => (dialog = "record")}>Record {a_doc}</button
      >
    </div>
  </div>
{/if}

<p class="hint muted">
  {text.docs_title} show for all dates; the Time filter doesn't apply here. Recorded
  and imported {text.docs_title.toLowerCase()} count as
  {is_bill ? "expenses" : "income"} on their date.
</p>

{#if dialog === "import"}
  <ImportDocs
    {text}
    accounts={data.accounts}
    ledger_account={data.ledger_account}
    onclose={() => (dialog = "")}
    ondone={done}
  />
{:else if dialog === "record"}
  <RecordDoc
    {text}
    {parties}
    accounts={data.accounts}
    onclose={() => (dialog = "")}
    ondone={done}
  />
{/if}
{#if matching}
  <MatchPayment
    {text}
    doc={matching}
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

  .party-head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem 2rem;
    align-items: center;
    margin-bottom: 1rem;
  }

  .party-head h2 {
    margin: 0;
    font-size: 1.3rem;
  }

  .party-head .stat {
    display: flex;
    flex-direction: column;
  }

  .party-head .stat span {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .party-head .stat strong {
    font-size: 1.2rem;
    font-variant-numeric: tabular-nums;
  }

  .back {
    margin-left: auto;
    font-weight: 600;
    color: var(--qb-accent);
  }

  .aging {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 8rem), 1fr));
    margin-bottom: 1rem;
    overflow: hidden;
    background: var(--qb-surface);
    border: 1px solid var(--border);
    border-radius: 10px;
  }

  .bucket {
    display: flex;
    flex-direction: column;
    padding: 0.5rem 0.8rem;
    border-right: 1px solid var(--border);
  }

  .bucket-label {
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .bucket-value {
    font-variant-numeric: tabular-nums;
  }

  .late .bucket-value {
    color: var(--error);
  }

  tfoot td {
    font-weight: 600;
    border-bottom: none;
  }

  .below {
    display: flex;
    justify-content: flex-end;
    margin-top: 0.6rem;
  }

  .cell-line {
    display: block;
    white-space: nowrap;
  }

  .doc-no {
    min-width: 8rem;
  }

  .party-cell {
    min-width: 12rem;
    white-space: normal;
  }

  .doc-no a {
    display: inline-block;
    max-width: 8rem;
    overflow-wrap: anywhere;
    white-space: normal;
  }

  .paid-with {
    white-space: nowrap;
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
