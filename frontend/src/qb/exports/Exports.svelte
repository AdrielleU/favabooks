<!--
  qb-fork: Export for CPA. The year-end package: a checklist of what to
  sort out first, then each report to view or download.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { HAVE_EXCEL } from "../../stores/index.ts";
  import type { QbCheck, QbExports, QbQboExport } from "../api.ts";
  import { get_qb_qbo_export } from "../api.ts";
  import Icon from "../Icon.svelte";
  import { download_csv } from "../reports/download.ts";
  import { qbo_files } from "./qbo.ts";

  let { data, checks }: { data: QbExports; checks: QbCheck[] } = $props();

  // Only years the books have transactions in, newest first.
  let year = $derived(data.year);
  let years = $derived(
    data.years.includes(year) || data.years.length === 0
      ? data.years
      : [year, ...data.years].toSorted((a, b) => b - a),
  );
  let ready = $derived(checks.filter((c) => c.ok).length);
  let year_end = $derived(`${year.toString()}-12-31`);

  /** Where to view each export as a report. */
  let views = $derived<Record<string, string>>({
    profit_loss: $url_for("qb_profit_loss/", { period: year.toString() }),
    balance_sheet: $url_for("qb_balance_sheet/", { as_of: year_end }),
    trial_balance: $url_for("qb_trial_balance/", { as_of: year_end }),
    general_ledger: $url_for("qb_general_ledger/", {
      period: year.toString(),
    }),
  });

  function pick_year(value: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("year", value);
    router.navigate(url);
  }

  let qbo_mode = $state<"transactions" | "balances">("transactions");
  let qbo = $state<QbQboExport | null>(null);
  let qbo_busy = $state(false);
  let files = $derived(qbo ? qbo_files(qbo) : []);
  let counts = $derived(
    qbo
      ? [
          `${qbo.accounts.length.toString()} accounts`,
          `${qbo.customers.length.toString()} customers`,
          `${qbo.vendors.length.toString()} vendors`,
          `${qbo.journals.toString()} journal entries`,
        ]
      : [],
  );

  async function prepare() {
    qbo_busy = true;
    try {
      qbo = await get_qb_qbo_export(year, qbo_mode);
    } catch (error) {
      notify_err(error);
    } finally {
      qbo_busy = false;
    }
  }

  const check_url = (c: QbCheck) => $url_for(`${c.report}/`, c.params);
</script>

<div class="head">
  <p class="muted">
    Everything your accountant asks for at year end. Work through the checklist,
    then send them the reports and your receipts folder.
  </p>
  <label class="year">
    Tax year
    <select
      value={year}
      onchange={(e) => {
        pick_year(e.currentTarget.value);
      }}
    >
      {#each years as y (y)}
        <option value={y}>{y}</option>
      {/each}
    </select>
  </label>
</div>

{#if data.years.length === 0}
  <p class="qb-card muted">No transactions yet: import some first.</p>
{/if}

<section class="qb-card">
  <div class="section-head">
    <h2><span class="step-no">1</span> Before you send</h2>
    <span class="progress" class:done={ready === checks.length}
      >{ready} of {checks.length} ready</span
    >
  </div>
  <ul class="checks">
    {#each checks as c (c.key)}
      <li class:ok={c.ok}>
        <span class="mark">
          <Icon name={c.ok ? "circle-check" : "triangle-alert"} size={18} />
        </span>
        <div class="text">
          <strong>{c.title}</strong>
          <span class="muted">{c.detail}</span>
        </div>
        {#if !c.ok}
          <a class="button qb-secondary small" href={check_url(c)}>Fix</a>
        {/if}
      </li>
    {/each}
  </ul>
</section>

<section class="qb-card">
  <h2><span class="step-no">2</span> Reports for {year}</h2>
  <ul class="reports">
    {#each data.exports as item (item.key)}
      <li>
        <div class="text">
          <strong>{item.title}</strong>
          <span class="muted">{item.description}</span>
        </div>
        <div class="links">
          {#if views[item.key]}
            <a class="button qb-secondary small" href={views[item.key]}>View</a>
          {/if}
          <a
            class="button qb-secondary small"
            href={$url_for("download-query/query_result.csv", {
              query_string: item.query,
            })}
            data-remote
          >
            <Icon name="download" size={14} /> CSV
          </a>
          {#if $HAVE_EXCEL}
            <a
              class="button qb-secondary small"
              href={$url_for("download-query/query_result.xlsx", {
                query_string: item.query,
              })}
              data-remote
            >
              <Icon name="download" size={14} /> Excel
            </a>
          {/if}
        </div>
      </li>
    {/each}
    <li>
      <div class="text">
        <strong>Transaction list</strong>
        <span class="muted"
          >Every transaction in {year} with category, payment account and receipt
          name. Export it from the page.</span
        >
      </div>
      <div class="links">
        <a
          class="button qb-secondary small"
          href={$url_for("qb_transactions/", { period: year.toString() })}
          >View</a
        >
      </div>
    </li>
    <li>
      <div class="text">
        <strong>Vendors and 1099s</strong>
        <span class="muted"
          >Spending per vendor and bank or check payments for 1099-NEC review.</span
        >
      </div>
      <div class="links">
        <a
          class="button qb-secondary small"
          href={$url_for("qb_vendors/", { period: year.toString() })}>View</a
        >
      </div>
    </li>
    <li>
      <div class="text">
        <strong>Receipts</strong>
        <span class="muted"
          >Your receipts are in the ledger's documents folder, filed by account;
          send that folder (or this year's files in it) along.</span
        >
      </div>
      <div class="links">
        <a class="button qb-secondary small" href={$url_for("documents/")}
          >Open</a
        >
      </div>
    </li>
  </ul>
  <p class="muted small-note">
    Downloads have the year's dates built in, so the header filters don't apply.
  </p>
</section>

<section class="qb-card">
  <h2><span class="step-no">3</span> For QuickBooks Online</h2>
  <p class="muted">
    If your accountant works in QuickBooks Online, these files load your books
    into it with QuickBooks' own importer.
  </p>
  <div class="qbo-mode">
    <label>
      <input
        type="radio"
        name="qbo-mode"
        value="transactions"
        bind:group={qbo_mode}
        onchange={() => (qbo = null)}
      />
      <span
        ><strong>Every transaction</strong> in {year}, one journal entry each
        (plus opening balances from earlier years)</span
      >
    </label>
    <label>
      <input
        type="radio"
        name="qbo-mode"
        value="balances"
        bind:group={qbo_mode}
        onchange={() => (qbo = null)}
      />
      <span
        ><strong>Year-end balances only</strong>: one journal entry with every
        balance on {year}-12-31, to start a QuickBooks file from there</span
      >
    </label>
  </div>
  {#if !qbo}
    <button
      type="button"
      class="qb-primary"
      disabled={qbo_busy || data.years.length === 0}
      onclick={prepare}
    >
      Prepare QuickBooks files
    </button>
  {:else}
    <ol class="qbo-steps">
      {#each files as [name, csv], i (name)}
        <li>
          <div class="text">
            <strong>{name}</strong>
            <span class="muted"
              >{counts[i]} · In QuickBooks: Settings → Import data → {[
                "Chart of accounts",
                "Customers",
                "Vendors",
                "Journal entries",
              ][i]}</span
            >
          </div>
          <button
            type="button"
            class="qb-secondary small"
            onclick={() => {
              download_csv(csv, name);
            }}
          >
            <Icon name="download" size={14} /> Download
          </button>
        </li>
      {/each}
    </ol>
    {#if qbo.skipped.length}
      <p class="warn">
        Left out ({qbo.skipped.length}): {qbo.skipped.join("; ")}
      </p>
    {/if}
    <p class="muted small-note">
      Import them in this order. Account names are flattened ("Legal - Startup")
      so the files agree with each other; account types are a best guess your
      accountant can change. Amounts are in {qbo.currency}.
    </p>
  {/if}
</section>

<style>
  .head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1.5rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .head p {
    max-width: 46rem;
    margin: 0;
  }

  .year {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-weight: 600;
  }

  .muted {
    color: var(--qb-muted);
  }

  section {
    margin-bottom: 1rem;
  }

  .section-head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    align-items: center;
    justify-content: space-between;
  }

  h2 {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin: 0 0 0.6rem;
    font-size: 1.05rem;
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

  .progress {
    padding: 0.15em 0.7em;
    font-size: 0.85em;
    font-weight: 600;
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 12%, transparent);
    border-radius: 999px;
  }

  .progress.done {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }

  ul {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.9rem;
    align-items: center;
    padding: 0.65rem 0;
    border-bottom: 1px solid var(--border-lighter);
  }

  li:last-child {
    border-bottom: none;
  }

  .text {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: min(100%, 16rem);
  }

  .mark {
    display: grid;
    color: var(--warning);
  }

  .ok .mark {
    color: var(--qb-accent);
  }

  .links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .small {
    display: inline-flex;
    gap: 0.3rem;
    align-items: center;
    padding: 0.3em 0.9em;
    font-size: 0.88em;
  }

  a.button.qb-secondary {
    color: var(--text-color);
    background: var(--qb-surface);
  }

  .qbo-mode {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 0.6rem 0 1rem;
  }

  .qbo-mode label {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
  }

  .qbo-steps {
    padding-left: 1.2rem;
    margin: 0;
  }

  .qbo-steps li {
    display: list-item;
  }

  .qbo-steps li > div,
  .qbo-steps li > button {
    display: inline-flex;
    vertical-align: middle;
  }

  .qbo-steps .text {
    flex-direction: column;
    width: calc(100% - 9rem);
  }

  .warn {
    color: var(--warning);
  }

  .small-note {
    margin: 0.8rem 0 0;
    font-size: 0.85em;
  }
</style>
