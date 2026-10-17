<!-- qb-fork: General ledger: every account's postings with balances. -->
<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";

  import { router } from "../../router.ts";
  import { accounts, years } from "../../stores/index.ts";
  import type { QbGeneralLedger } from "../api.ts";
  import PeriodPicker from "../docs/PeriodPicker.svelte";
  import type { Period } from "../docs/periods.ts";
  import { iso, to_csv } from "../docs/periods.ts";
  import { money, short_date } from "../format.ts";
  import { leaf } from "../transactions/helpers.ts";
  import { download_csv } from "./download.ts";
  import { date_range_label, months_of_years } from "./helpers.ts";
  import ReportFrame from "./ReportFrame.svelte";

  let {
    data,
    period,
    today,
    account,
  }: {
    data: QbGeneralLedger;
    period: Period;
    today: Date;
    account: string;
  } = $props();

  const collapsed = new SvelteSet<string>();
  const fmt = (n: number) => money(n, data.currency);
  let roots = $derived([
    ...new Set($accounts.map((a) => a.split(":")[0] ?? a)),
  ]);

  function toggle(name: string) {
    if (!collapsed.delete(name)) {
      collapsed.add(name);
    }
  }

  function collapse_all(names: string[]) {
    collapsed.clear();
    for (const name of names) {
      collapsed.add(name);
    }
  }

  function export_csv() {
    download_csv(
      to_csv([
        ["Account", "Date", "Payee", "Memo", "Split", "Amount", "Balance"],
        ...data.accounts.flatMap((a) => [
          [
            a.account,
            "",
            "Beginning balance",
            "",
            "",
            "",
            a.opening.toFixed(2),
          ],
          ...a.rows.map((r) => [
            a.account,
            iso(r.date),
            r.payee,
            r.narration,
            r.split.join(" "),
            r.amount.toFixed(2),
            r.balance.toFixed(2),
          ]),
          [a.account, "", "Ending balance", "", "", "", a.closing.toFixed(2)],
        ]),
      ]),
      `general-ledger-${period.key}.csv`,
    );
  }
</script>

<ReportFrame
  company={data.company}
  title="General ledger"
  subtitle={date_range_label(data.start, data.end)}
  unconverted={data.unconverted}
  onexport={export_csv}
  onexpand={() => {
    collapsed.clear();
  }}
  oncollapse={() => {
    collapse_all(data.accounts.map((a) => a.account));
  }}
>
  {#snippet options()}
    <PeriodPicker {period} {today} dates={months_of_years($years, today)} />
    <label class="opt">
      Accounts
      <select
        value={account}
        onchange={(e) => {
          const url = new URL(window.location.href);
          if (e.currentTarget.value) {
            url.searchParams.set("account_name", e.currentTarget.value);
          } else {
            url.searchParams.delete("account_name");
          }
          router.navigate(url);
        }}
      >
        <option value="">All accounts</option>
        {#each roots as root (root)}<option value={root}>{root}</option>{/each}
        {#each $accounts as a (a)}<option value={a}>{a}</option>{/each}
      </select>
    </label>
  {/snippet}
  {#if data.accounts.length}
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Payee / memo</th>
          <th>Split</th>
          <th class="num">Amount</th>
          <th class="num">Balance</th>
        </tr>
      </thead>
      {#each data.accounts as a (a.account)}
        {@const closed = collapsed.has(a.account)}
        <tbody>
          <tr class="acct">
            <td colspan="4">
              <button
                type="button"
                class="toggle"
                aria-expanded={!closed}
                onclick={() => {
                  toggle(a.account);
                }}>{closed ? "▸" : "▾"}</button
              >
              {a.account}
              <span class="muted">({a.rows.length})</span>
            </td>
            <td class="num">{closed ? fmt(a.closing) : ""}</td>
          </tr>
          {#if !closed}
            <tr class="muted-row">
              <td></td>
              <td>Beginning balance</td>
              <td></td>
              <td></td>
              <td class="num">{fmt(a.opening)}</td>
            </tr>
            {#each a.rows as r, i (`${r.entry_hash}-${i.toString()}`)}
              <tr>
                <td class="nowrap">{short_date(r.date)}</td>
                <td>
                  <a href={`#context-${r.entry_hash}`}
                    >{r.payee || r.narration}</a
                  >
                  {#if r.payee && r.narration}<span class="muted sub"
                      >{r.narration}</span
                    >{/if}
                </td>
                <td class="muted">{r.split.map(leaf).join(", ")}</td>
                <td class="num">{fmt(r.amount)}</td>
                <td class="num">{fmt(r.balance)}</td>
              </tr>
            {/each}
            <tr class="end">
              <td></td>
              <td>Ending balance</td>
              <td></td>
              <td class="num"
                >{fmt(
                  a.rows.reduce((s, r) => s + Math.round(r.amount * 100), 0) /
                    100,
                )}</td
              >
              <td class="num">{fmt(a.closing)}</td>
            </tr>
          {/if}
        </tbody>
      {/each}
    </table>
  {:else}
    <p class="muted">No activity in this period.</p>
  {/if}
</ReportFrame>

<style>
  .opt {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0;
    font-variant-numeric: tabular-nums;
    border: none;
  }

  th,
  td {
    padding: 0.3em 0.6em;
    vertical-align: top;
    border: none;
  }

  th {
    font-size: 0.85em;
    font-weight: 600;
    color: var(--text-color-lighter);
    text-align: left;
    border-bottom: 1px solid var(--border-darker);
  }

  .num {
    text-align: right;
    white-space: nowrap;
  }

  .nowrap {
    white-space: nowrap;
  }

  .acct td {
    padding-top: 1em;
    font-weight: 700;
  }

  .end td {
    font-weight: 600;
    border-top: 1px solid var(--border);
  }

  .muted,
  .muted-row td {
    color: var(--qb-muted);
  }

  .sub {
    display: block;
    font-size: 0.85em;
  }

  td a {
    color: inherit;
  }

  .toggle {
    width: 1.2em;
    padding: 0;
    color: var(--qb-muted);
    background: none;
  }
</style>
