<!-- qb-fork: Trial balance, debit and credit columns. -->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import type { QbTrialBalance } from "../api.ts";
  import { iso, to_csv } from "../docs/periods.ts";
  import { money, short_date } from "../format.ts";
  import AsOfPicker from "./AsOfPicker.svelte";
  import { download_csv } from "./download.ts";
  import { date_range_label } from "./helpers.ts";
  import ReportFrame from "./ReportFrame.svelte";

  let { data, today }: { data: QbTrialBalance; today: Date } = $props();

  const fmt = (n: number) => (n ? money(n, data.currency) : "");
  let computed = $derived((account: string) => account.includes("(computed)"));

  function drill(account: string): string {
    return $url_for("qb_transactions/", {
      account,
      period: "custom",
      to: iso(data.as_of),
    });
  }

  function export_csv() {
    download_csv(
      to_csv([
        ["Account", "Debit", "Credit"],
        ...data.rows.map((r) => [
          r.account,
          r.debit ? r.debit.toFixed(2) : "",
          r.credit ? r.credit.toFixed(2) : "",
        ]),
        ["Total", data.debit.toFixed(2), data.credit.toFixed(2)],
      ]),
      `trial-balance-${iso(data.as_of)}.csv`,
    );
  }
</script>

<ReportFrame
  company={data.company}
  title="Trial balance"
  subtitle={date_range_label(null, data.as_of)}
  unconverted={data.unconverted}
  onexport={export_csv}
>
  {#snippet options()}
    <AsOfPicker value={iso(data.as_of)} {today} />
  {/snippet}
  <table>
    <thead>
      <tr>
        <th>Account</th>
        <th class="num">Debit</th>
        <th class="num">Credit</th>
      </tr>
    </thead>
    <tbody>
      {#each data.rows as row (row.account)}
        <tr>
          <td>
            {#if computed(row.account)}
              Retained earnings
            {:else}
              <a href={drill(row.account)}>{row.account}</a>
            {/if}
          </td>
          <td class="num">{fmt(row.debit)}</td>
          <td class="num">{fmt(row.credit)}</td>
        </tr>
      {/each}
    </tbody>
    <tfoot>
      <tr>
        <td>Total</td>
        <td class="num">{money(data.debit, data.currency)}</td>
        <td class="num">{money(data.credit, data.currency)}</td>
      </tr>
    </tfoot>
  </table>
  <p class="note">
    Income and expense accounts cover the fiscal year from
    {short_date(data.fiscal_start)}; earlier years are in retained earnings.
    {#if Math.round((data.debit - data.credit) * 100) !== 0}
      <strong class="warn">Debits and credits don't match.</strong>
    {/if}
  </p>
</ReportFrame>

<style>
  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0;
    font-variant-numeric: tabular-nums;
    border: none;
  }

  th,
  td {
    padding: 0.35em 0.6em;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-size: 0.85em;
    font-weight: 600;
    color: var(--text-color-lighter);
    text-align: left;
  }

  .num {
    text-align: right;
    white-space: nowrap;
  }

  td a {
    color: inherit;
  }

  td a:hover {
    color: var(--qb-accent);
    text-decoration: underline;
  }

  tfoot td {
    font-weight: 700;
    border-top: 1px solid var(--border-darker);
    border-bottom: 3px double var(--border-darker);
  }

  .note {
    margin: 1rem 0 0;
    font-size: 0.85em;
    color: var(--qb-muted);
  }

  .warn {
    color: var(--error);
  }
</style>
