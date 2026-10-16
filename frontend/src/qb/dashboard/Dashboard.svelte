<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { ctx } from "../../stores/format.ts";
  import type { QbDashboard } from "../api.ts";

  let { data }: { data: QbDashboard } = $props();

  let fmt = $derived((n: number) => $ctx.amount(n, data.currency));
  let month_name = (month: string, style: "long" | "short" = "long") =>
    new Date(`${month}-01T00:00:00Z`).toLocaleDateString(undefined, {
      month: style,
      year: "numeric",
      timeZone: "UTC",
    });
  let leaf = (account: string) => account.split(":").slice(1).join(":");

  let total_cash = $derived(
    data.balances.reduce((sum, row) => sum + row.amount, 0),
  );
  let max_expense = $derived(
    Math.max(...data.top_expenses.map((row) => row.amount), 1),
  );
  let pnl_rows = $derived([
    ["Income", data.this_month.income, data.last_month.income],
    ["Expenses", data.this_month.expenses, data.last_month.expenses],
    ["Net profit", data.this_month.net, data.last_month.net],
  ] as const);
</script>

<p class="period">
  {month_name(data.this_month.month)}
  <span>· set the Time filter above to see another month</span>
</p>

<div class="grid">
  <section class="qb-card">
    <h3>Bank and Stripe balances</h3>
    {#if data.balances.length}
      <table>
        <tbody>
          {#each data.balances as row (row.account)}
            <tr>
              <td>
                <a href={$url_for(`account/${row.account}/`)}>
                  {leaf(row.account)}
                </a>
              </td>
              <td class="num">{fmt(row.amount)}</td>
            </tr>
          {/each}
        </tbody>
        <tfoot>
          <tr>
            <td>Total</td>
            <td class="num">{fmt(total_cash)}</td>
          </tr>
        </tfoot>
      </table>
      <p class="note">As of {data.balances_date.toISOString().slice(0, 10)}</p>
    {:else}
      <p class="empty">No accounts under Assets:Bank or Assets:Stripe.</p>
    {/if}
  </section>

  <section class="qb-card">
    <h3>Profit and loss</h3>
    <table>
      <thead>
        <tr>
          <th></th>
          <th class="num">{month_name(data.this_month.month, "short")}</th>
          <th class="num">{month_name(data.last_month.month, "short")}</th>
        </tr>
      </thead>
      <tbody>
        {#each pnl_rows as [label, current, previous] (label)}
          <tr class:net={label === "Net profit"}>
            <td>{label}</td>
            <td class="num" class:negative={current < 0}>{fmt(current)}</td>
            <td class="num" class:negative={previous < 0}>{fmt(previous)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    <p class="note">
      <a href={$url_for("income_statement/")}>Full profit and loss</a>
    </p>
  </section>

  <a class="qb-card stat" href={$url_for("qb_review/")}>
    <h3>For review</h3>
    <strong class:attention={data.review_count > 0}>{data.review_count}</strong>
    <span>transactions flagged ! waiting to be categorised</span>
  </a>

  <section class="qb-card wide">
    <h3>Expenses by category, {month_name(data.this_month.month)}</h3>
    {#if data.top_expenses.length}
      <ul class="bars">
        {#each data.top_expenses as row (row.account)}
          <li>
            <a href={$url_for(`account/${row.account}/`)}>{leaf(row.account)}</a
            >
            <span class="bar">
              <span style:width="{(row.amount / max_expense) * 100}%"></span>
            </span>
            <span class="num">{fmt(row.amount)}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="empty">No expenses this month.</p>
    {/if}
  </section>

  <a class="qb-card stat" href={$url_for("errors/")}>
    <h3>Ledger errors</h3>
    <strong class:error={data.error_count > 0}>{data.error_count}</strong>
    <span
      >{data.error_count
        ? "fix these before closing the month"
        : "all clear"}</span
    >
  </a>
</div>

<style>
  .period {
    margin: 0 0 1rem;
    font-size: 1.2em;
    font-weight: 500;
  }

  .period span {
    font-size: 0.75em;
    font-weight: normal;
    color: var(--text-color-lightest);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
    gap: 1rem;
    align-items: start;
  }

  .wide {
    grid-column: span 2;
  }

  @media (width <= 1100px) {
    .wide {
      grid-column: auto;
    }
  }

  h3 {
    margin: 0 0 0.75rem;
    font-size: 0.95em;
    font-weight: 500;
    color: var(--text-color-lighter);
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    border: none;
  }

  th,
  td {
    padding: 0.3em 0;
    background: none;
    border: none;
  }

  th {
    font-weight: normal;
    color: var(--text-color-lightest);
  }

  .num {
    padding-left: 1.25em;
    font-family: var(--font-family-monospaced);
    text-align: right;
    white-space: nowrap;
  }

  tfoot td,
  .net td {
    font-weight: 500;
    border-top: 1px solid var(--border);
  }

  .negative {
    color: var(--diff-negative);
  }

  .note,
  .empty {
    margin: 0.5rem 0 0;
    font-size: 0.85em;
    color: var(--text-color-lightest);
  }

  .bars {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 14em) minmax(4em, 1fr) auto;
    gap: 0.75em;
    align-items: center;
    padding: 0.2em 0;
  }

  .bars a {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bar {
    height: 0.8em;
    background: var(--background-darker);
    border-radius: 4px;
  }

  .bar span {
    display: block;
    height: 100%;
    background: var(--qb-accent);
    border-radius: 4px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    color: inherit;
    text-decoration: none;
  }

  .stat:hover {
    border-color: var(--qb-accent);
  }

  .stat strong {
    font-size: 2.2em;
    font-weight: 500;
    line-height: 1.1;
  }

  .stat span {
    color: var(--text-color-lightest);
  }

  .attention {
    color: var(--qb-accent);
  }

  .error {
    color: var(--error);
  }
</style>
