<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import type { QbDashboard } from "../api.ts";
  import { change, money, money_short, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import { account_label } from "../nicknames.ts";

  let { data }: { data: QbDashboard } = $props();

  let cur = $derived(data.currency);
  const month_name = (month: string, style: "long" | "short" = "long") =>
    new Date(`${month}-01T00:00:00Z`).toLocaleDateString(undefined, {
      month: style,
      year: "numeric",
      timeZone: "UTC",
    });
  const leaf = (account: string) => account.split(":").slice(1).join(":");

  let total_cash = $derived(
    data.balances.reduce((sum, row) => sum + row.amount, 0),
  );
  let total_expenses = $derived(
    data.top_expenses.reduce((sum, row) => sum + row.amount, 0),
  );
  let max_expense = $derived(
    Math.max(...data.top_expenses.map((row) => row.amount), 1),
  );
  let pnl_max = $derived(
    Math.max(
      data.this_month.income,
      data.this_month.expenses,
      data.last_month.income,
      data.last_month.expenses,
      1,
    ),
  );
  let kpis = $derived([
    {
      label: "Cash on hand",
      value: total_cash,
      delta: null,
      note: `Bank and Stripe, ${short_date(data.balances_date)}`,
      good_when_up: true,
    },
    {
      label: "Income",
      value: data.this_month.income,
      delta: change(data.this_month.income, data.last_month.income),
      note: month_name(data.this_month.month),
      good_when_up: true,
    },
    {
      label: "Expenses",
      value: data.this_month.expenses,
      delta: change(data.this_month.expenses, data.last_month.expenses),
      note: month_name(data.this_month.month),
      good_when_up: false,
    },
    {
      label: "Net profit",
      value: data.this_month.net,
      delta: change(data.this_month.net, data.last_month.net),
      note: month_name(data.this_month.month),
      good_when_up: true,
    },
  ]);
</script>

<div class="intro">
  <h2>Business overview</h2>
  <span class="muted">
    {month_name(data.this_month.month)} · use the Time filter to see another month
  </span>
</div>

<section class="kpis">
  {#each kpis as kpi (kpi.label)}
    <div class="qb-card kpi">
      <span class="kpi-label">{kpi.label}</span>
      <strong class:negative={kpi.value < 0}
        >{money_short(kpi.value, cur)}</strong
      >
      <span class="kpi-note">
        {#if kpi.delta !== null}
          {@const up = kpi.delta >= 0}
          <span
            class="delta"
            class:good={up === kpi.good_when_up}
            class:bad={up !== kpi.good_when_up}
          >
            {up ? "▲" : "▼"}
            {Math.abs(kpi.delta * 100).toFixed(0)}%
          </span>
          vs last month ·
        {/if}
        {kpi.note}
      </span>
    </div>
  {/each}
</section>

<div class="grid">
  <section class="qb-card">
    <div class="card-head">
      <h3>Bank accounts</h3>
      <a href={$url_for("qb_review/")}>Go to banking</a>
    </div>
    {#if data.balances.length}
      <ul class="accounts">
        {#each data.balances as row (row.account)}
          <li>
            <span class="acct-icon"><Icon name="landmark" size={16} /></span>
            <a
              href={$url_for("qb_register/", { account_name: row.account })}
              title={row.account}
            >
              {$account_label(row.account)}
            </a>
            <span class="amount" class:negative={row.amount < 0}>
              {money(row.amount, cur)}
            </span>
          </li>
        {/each}
      </ul>
      <p class="foot">
        Total <strong>{money(total_cash, cur)}</strong>
      </p>
    {:else}
      <p class="muted">No accounts under Assets:Bank or Assets:Stripe.</p>
    {/if}
  </section>

  <section class="qb-card">
    <div class="card-head">
      <h3>Profit and loss</h3>
      <a href={$url_for("qb_profit_loss/")}>View report</a>
    </div>
    <p class="big" class:negative={data.this_month.net < 0}>
      {money(data.this_month.net, cur)}
      <span class="muted"
        >net profit, {month_name(data.this_month.month, "short")}</span
      >
    </p>
    {#each [data.this_month, data.last_month] as month (month.month)}
      <div class="pnl">
        <span class="pnl-month">{month_name(month.month, "short")}</span>
        <div class="pnl-bars">
          <span
            class="bar income"
            style:width="{(month.income / pnl_max) * 100}%"
          ></span>
          <span
            class="bar expenses"
            style:width="{(month.expenses / pnl_max) * 100}%"
          ></span>
        </div>
        <span class="pnl-values">
          {money_short(month.income, cur)}<br />{money_short(
            month.expenses,
            cur,
          )}
        </span>
      </div>
    {/each}
    <p class="legend">
      <span class="dot income"></span>Income
      <span class="dot expenses"></span>Expenses
    </p>
  </section>

  <div class="stack">
    <section class="qb-card action">
      <span class="action-icon" class:attention={data.review_count > 0}>
        <Icon name="inbox" size={22} />
      </span>
      <div>
        <h3>{data.review_count} to review</h3>
        <p class="muted">Imported transactions waiting to be categorised.</p>
      </div>
      <a class="button qb-primary" href={$url_for("qb_review/")}>Review</a>
    </section>
    <section class="qb-card action">
      <span class="action-icon" class:error={data.error_count > 0}>
        <Icon
          name={data.error_count ? "triangle-alert" : "circle-check"}
          size={22}
        />
      </span>
      <div>
        <h3>
          {data.error_count
            ? `${data.error_count.toString()} ledger errors`
            : "Books are balanced"}
        </h3>
        <p class="muted">
          {data.error_count
            ? "Fix these before closing the month."
            : "No errors in the ledger."}
        </p>
      </div>
      {#if data.error_count}
        <a class="button qb-secondary" href={$url_for("errors/")}>View</a>
      {/if}
    </section>
    <section class="qb-card action">
      <span class="action-icon"><Icon name="upload" size={22} /></span>
      <div>
        <h3>Import bank files</h3>
        <p class="muted">Bank, card and Stripe downloads.</p>
      </div>
      <a class="button qb-secondary" href={$url_for("import/")}>Import</a>
    </section>
  </div>
  <section class="qb-card wide">
    <div class="card-head">
      <h3>Expenses</h3>
      <span class="muted">{month_name(data.this_month.month, "short")}</span>
    </div>
    {#if data.top_expenses.length}
      <p class="big">
        {money(total_expenses, cur)}
        <span class="muted">top {data.top_expenses.length} categories</span>
      </p>
      <ul class="bars">
        {#each data.top_expenses as row (row.account)}
          <li>
            <a href={$url_for(`account/${row.account}/`)}>{leaf(row.account)}</a
            >
            <span class="track">
              <span style:width="{(row.amount / max_expense) * 100}%"></span>
            </span>
            <span class="amount">{money(row.amount, cur)}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="muted">No expenses this month.</p>
    {/if}
  </section>
</div>

<style>
  .intro {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.75rem;
    align-items: baseline;
    margin-bottom: 1rem;
  }

  h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
  }

  h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
  }

  .muted {
    font-size: 0.9em;
    font-weight: normal;
    color: var(--qb-muted);
  }

  .negative {
    color: var(--diff-negative);
  }

  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 13rem), 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .kpi {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .kpi-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--qb-muted);
  }

  .kpi strong {
    font-size: 1.75rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }

  .kpi-note {
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .delta {
    font-weight: 600;
  }

  .delta.good {
    color: var(--diff-positive);
  }

  .delta.bad {
    color: var(--diff-negative);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
    gap: 1rem;
    align-items: start;
  }

  .card-head {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
    justify-content: space-between;
    padding-bottom: 0.7rem;
    margin-bottom: 0.9rem;
    border-bottom: 1px solid var(--border-lighter);
  }

  .card-head a {
    font-size: 0.85rem;
    font-weight: 600;
  }

  .accounts {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .accounts li {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    padding: 0.55rem 0;
    border-bottom: 1px solid var(--border-lighter);
  }

  .accounts a {
    flex: 1;
    font-weight: 500;
  }

  .acct-icon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  .amount {
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }

  .foot {
    margin: 0.7rem 0 0;
    text-align: right;
  }

  .big {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
    margin: 0 0 0.9rem;
    font-size: 1.5rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .pnl {
    display: grid;
    grid-template-columns: 4.5rem 1fr auto;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 0.6rem;
  }

  .pnl-month {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .pnl-bars {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .bar {
    display: block;
    min-width: 2px;
    height: 12px;
    border-radius: 3px;
  }

  .income,
  .dot.income {
    background: var(--qb-accent);
  }

  .expenses,
  .dot.expenses {
    background: light-dark(hsl(205deg 70% 55%), hsl(205deg 70% 62%));
  }

  .pnl-values {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
    line-height: 16px;
    color: var(--qb-muted);
    text-align: right;
  }

  .legend {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    margin: 0.6rem 0 0;
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    margin-left: 0.6rem;
    border-radius: 50%;
  }

  .dot.income {
    margin-left: 0;
  }

  .bars {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 9rem) minmax(4em, 1fr) 6.5rem;
    gap: 0.75rem;
    align-items: center;
    padding: 0.25rem 0;
    font-size: 0.92rem;
  }

  .bars a {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .track {
    height: 10px;
    background: var(--background-darker);
    border-radius: 5px;
  }

  .track span {
    display: block;
    height: 100%;
    background: var(--qb-accent);
    border-radius: 5px;
  }

  .wide {
    grid-column: span 2;
  }

  @media (width <= 1180px) {
    .wide {
      grid-column: auto;
    }
  }

  .stack {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .action {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.9rem;
    align-items: center;
  }

  .action p {
    margin: 0.15rem 0 0;
  }

  .action-icon {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    color: var(--qb-muted);
    background: var(--background-darker);
    border-radius: 50%;
  }

  .action-icon.attention {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }

  .action-icon.error {
    color: var(--error);
    background: color-mix(in srgb, var(--error) 12%, transparent);
  }

  a.button {
    color: var(--button-color);
    white-space: nowrap;
    background: var(--button-background);
  }

  a.button.qb-secondary {
    color: var(--text-color);
    background: var(--qb-surface);
  }
</style>
