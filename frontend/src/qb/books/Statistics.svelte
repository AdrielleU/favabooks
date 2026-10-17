<!--
  qb-fork: Statistics. How complete and up to date the books are: counts,
  transactions per month, and which bank or card accounts have gone quiet.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import type { QbStatistics } from "../api.ts";
  import TrendChart from "../charts/TrendChart.svelte";
  import { short_date } from "../format.ts";
  import { account_label } from "../nicknames.ts";

  let { data }: { data: QbStatistics } = $props();

  /** Days without activity after which an account may have missed imports. */
  const QUIET = 45;
  let show_all = $state(false);
  let months = $derived(
    data.months.map((m) =>
      m.month.toLocaleDateString("en-US", {
        month: "short",
        year: "2-digit",
        timeZone: "UTC",
      }),
    ),
  );
  let quiet = $derived(
    data.accounts.filter((a) => a.days === null || a.days > QUIET),
  );
  let postings = $derived(
    show_all ? data.postings : data.postings.slice(0, 12),
  );
  let entry_total = $derived(
    Object.values(data.entries).reduce((sum, n) => sum + n, 0),
  );
  const LABELS: Record<string, string> = {
    Transaction: "Transactions",
    Document: "Documents (receipts and statements)",
    Open: "Account openings",
    Close: "Account closings",
    Balance: "Balance checks",
    Note: "Notes",
    Custom: "Settings and custom entries",
    Price: "Prices",
    Event: "Events",
    Commodity: "Currency definitions",
    Pad: "Pads",
    Query: "Saved queries",
  };
</script>

<div class="cards">
  <a class="qb-card stat" href={$url_for("qb_transactions/")}>
    <span>Transactions</span><strong>{data.transactions}</strong>
    <small class="muted"
      >{data.first_date && data.last_date
        ? `${short_date(data.first_date)} – ${short_date(data.last_date)}`
        : "None yet"}</small
    >
  </a>
  <a
    class="qb-card stat"
    href={$url_for("qb_transactions/", { kind: "review" })}
  >
    <span>Need review</span>
    <strong class:warn={data.to_review > 0}>{data.to_review}</strong>
  </a>
  <a class="qb-card stat" href={$url_for("qb_chart/")}>
    <span>Open accounts</span><strong>{data.open_accounts}</strong>
  </a>
  <a class="qb-card stat" href={$url_for("documents/")}>
    <span>Receipts & documents</span><strong>{data.documents}</strong>
  </a>
  <a class="qb-card stat" href={$url_for("errors/")}>
    <span>Errors</span>
    <strong class:bad={data.errors > 0}>{data.errors}</strong>
  </a>
</div>

{#if data.months.length}
  <div class="qb-card panel">
    <h3>Transactions per month</h3>
    <TrendChart
      labels={months}
      values={{
        transactions: data.months.map((m) => m.transactions),
        to_review: data.months.map((m) => m.to_review),
      }}
      series={[
        {
          key: "transactions",
          label: "Transactions",
          color: "#2563eb",
          kind: "bar",
        },
        {
          key: "to_review",
          label: "Still need review",
          color: "#f59e0b",
          kind: "bar",
        },
      ]}
      currency=""
      format={(n: number) => Math.round(n).toString()}
      height={200}
    />
  </div>
{/if}

<div class="grid">
  <div class="qb-card panel">
    <h3>Bank and card activity</h3>
    <p class="muted small">
      When each account last had a transaction. One that's been quiet for more
      than {QUIET} days may have missed an import.
      {#if quiet.length}<strong class="warn">{quiet.length} to check.</strong
        >{/if}
    </p>
    <table>
      <tbody>
        {#each data.accounts as a (a.account)}
          <tr>
            <td>
              <a href={$url_for("qb_register/", { account_name: a.account })}
                >{$account_label(a.account)}</a
              >
            </td>
            <td class="num">{a.postings}</td>
            <td class="nowrap">
              {#if a.last_date === null}
                <span class="badge bad">No activity</span>
              {:else}
                {short_date(a.last_date)}
                {#if (a.days ?? 0) > QUIET}
                  <span class="badge warn">{a.days} days ago</span>
                {/if}
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <div class="qb-card panel">
    <h3>What's in the books</h3>
    <table>
      <tbody>
        {#each Object.entries(data.entries) as [kind, n] (kind)}
          <tr>
            <td>{LABELS[kind] ?? kind}</td>
            <td class="num">{n}</td>
          </tr>
        {/each}
        <tr class="total">
          <td>All entries</td>
          <td class="num">{entry_total}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="qb-card panel">
    <h3>Busiest accounts</h3>
    <table>
      <tbody>
        {#each postings as [account, n] (account)}
          <tr>
            <td>
              <a href={$url_for("qb_transactions/", { account })}
                >{$account_label(account)}</a
              >
            </td>
            <td class="num">{n}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if data.postings.length > 12}
      <button type="button" class="link" onclick={() => (show_all = !show_all)}
        >{show_all
          ? "Show fewer"
          : `Show all ${data.postings.length.toString()}`}</button
      >
    {/if}
  </div>
</div>

<style>
  .muted {
    color: var(--qb-muted);
  }

  .small {
    font-size: 0.88em;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
    gap: 0.8rem;
    margin-bottom: 1rem;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    color: inherit;
  }

  .stat span {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .stat strong {
    font-size: 1.4rem;
    font-weight: 650;
  }

  .warn {
    color: var(--warning);
  }

  .bad {
    color: var(--error);
  }

  .panel {
    margin-bottom: 1rem;
  }

  h3 {
    margin: 0 0 0.6rem;
    font-size: 1rem;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr));
    gap: 1rem;
  }

  .grid .panel {
    margin: 0;
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0;
    border: none;
  }

  td {
    padding: 0.4em 0.5em;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  td a {
    color: inherit;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .nowrap {
    white-space: nowrap;
  }

  .total td {
    font-weight: 700;
    border-bottom: none;
  }

  .badge {
    display: table;
    padding: 0 0.5em;
    margin-top: 0.15em;
    font-size: 0.75em;
    font-weight: 600;
    border: 1px solid currentcolor;
    border-radius: 999px;
  }

  .link {
    padding: 0;
    margin-top: 0.6rem;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }
</style>
