<!-- qb-fork: Balance sheet, QuickBooks style. -->
<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";

  import { url_for } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import type { QbBalancePoint, QbStatement } from "../api.ts";
  import DonutChart from "../charts/DonutChart.svelte";
  import type { Slice } from "../charts/data.ts";
  import { change_text, top_slices } from "../charts/data.ts";
  import TrendChart from "../charts/TrendChart.svelte";
  import { iso, to_csv } from "../docs/periods.ts";
  import { money } from "../format.ts";
  import AsOfPicker from "./AsOfPicker.svelte";
  import ChartsPanel from "./ChartsPanel.svelte";
  import { download_csv } from "./download.ts";
  import {
    date_range_label,
    line_row,
    parents,
    statement_rows,
    tree_rows,
  } from "./helpers.ts";
  import ReportFrame from "./ReportFrame.svelte";
  import Statement from "./Statement.svelte";

  let {
    statement,
    history,
    today,
    compare,
  }: {
    statement: QbStatement;
    history: QbBalancePoint[];
    today: Date;
    compare: boolean;
  } = $props();

  let currency = $derived(statement.currency);
  let first = $derived(history[0]);
  let last = $derived(history[history.length - 1]);
  let since = $derived(
    first
      ? `since ${first.date.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" })}`
      : "",
  );
  let cards = $derived(
    last && first
      ? [
          {
            label: "Total assets",
            value: money(last.assets, currency),
            change: change_text(last.assets, first.assets, since),
            good: last.assets >= first.assets,
          },
          {
            label: "Total liabilities",
            value: money(last.liabilities, currency),
            change: change_text(last.liabilities, first.liabilities, since),
            good: last.liabilities <= first.liabilities,
          },
          {
            label: "Net worth (equity)",
            value: money(last.equity, currency),
            change: change_text(last.equity, first.equity, since),
            good: last.equity >= first.equity,
          },
        ]
      : [],
  );
  let owe = $derived(
    top_slices(
      statement.blocks.find((b) => b.key === "liabilities")?.node ?? null,
      0,
    ),
  );
  let own = $derived(
    top_slices(
      statement.blocks.find((b) => b.key === "assets")?.node ?? null,
      0,
    ),
  );
  let side_slices = $derived(own.length ? own : owe);
  const month = (d: Date) =>
    d.toLocaleDateString("en-US", {
      month: "short",
      year: "2-digit",
      timeZone: "UTC",
    });

  function show_as_of(date: Date) {
    const url = new URL(window.location.href);
    url.searchParams.set("as_of", iso(date));
    router.navigate(url);
  }

  const collapsed = new SvelteSet<string>();
  let as_of = $derived(statement.columns[0]?.end ?? today);
  let check = $derived.by(() => {
    const total = (key: string) =>
      statement.blocks.find((b) => b.key === key)?.amounts[0] ?? 0;
    return Math.round((total("assets") - total("liabilities_equity")) * 100);
  });

  function toggle(account: string) {
    if (!collapsed.delete(account)) {
      collapsed.add(account);
    }
  }

  function collapse_all(names: string[]) {
    collapsed.clear();
    for (const name of names) {
      collapsed.add(name);
    }
  }

  function drill(account: string, i: number): string {
    const column = statement.columns[i];
    return $url_for("qb_transactions/", {
      account,
      period: "custom",
      to: column ? iso(column.end) : "",
    });
  }

  function export_csv() {
    const sections = statement.blocks.map((b) =>
      b.kind === "section"
        ? tree_rows(b.title, b.node, new Set(), b.amounts)
        : [line_row(b.key, b.title, b.amounts)],
    );
    download_csv(
      to_csv(
        statement_rows(
          statement.columns.map((c) => c.label),
          sections,
        ),
      ),
      `balance-sheet-${iso(as_of)}.csv`,
    );
  }
</script>

<ReportFrame
  company={statement.company}
  title="Balance sheet"
  subtitle={date_range_label(null, as_of)}
  unconverted={statement.unconverted}
  onexport={export_csv}
  onexpand={() => {
    collapsed.clear();
  }}
  oncollapse={() => {
    collapse_all(statement.blocks.flatMap((b) => parents(b.node)));
  }}
>
  {#snippet charts()}
    <ChartsPanel
      kpis={cards}
      trend_title="Assets, liabilities and net worth"
      side_title={own.length ? "What you own" : "What you owe"}
    >
      {#snippet trend()}
        <TrendChart
          labels={history.map((p) => month(p.date))}
          values={{
            assets: history.map((p) => p.assets),
            liabilities: history.map((p) => p.liabilities),
            equity: history.map((p) => p.equity),
          }}
          series={[
            { key: "assets", label: "Assets", color: "#10b981", kind: "bar" },
            {
              key: "liabilities",
              label: "Liabilities",
              color: "#ef4444",
              kind: "bar",
            },
            {
              key: "equity",
              label: "Net worth",
              color: "#2563eb",
              kind: "line",
            },
          ]}
          {currency}
          onselect={(i: number) => {
            const p = history[i];
            if (p) {
              show_as_of(p.date);
            }
          }}
        />
      {/snippet}
      {#snippet side()}
        {#if side_slices.length}
          <DonutChart
            slices={side_slices}
            {currency}
            title={own.length ? "What you own" : "What you owe"}
            onselect={(s: Slice) => {
              if (s.account) {
                router.navigate(drill(s.account, 0));
              }
            }}
          />
        {:else}
          <p class="muted">Nothing to show on this date.</p>
        {/if}
      {/snippet}
    </ChartsPanel>
  {/snippet}
  {#snippet options()}
    <AsOfPicker value={iso(as_of)} {today} />
    <label class="opt">
      <input
        type="checkbox"
        checked={compare}
        onchange={(e) => {
          const url = new URL(window.location.href);
          if (e.currentTarget.checked) {
            url.searchParams.set("compare", "1");
          } else {
            url.searchParams.delete("compare");
          }
          router.navigate(url);
        }}
      />
      Compare with a year earlier
    </label>
  {/snippet}
  <Statement
    {statement}
    {collapsed}
    ontoggle={toggle}
    {drill}
    show_change={compare}
  />
  {#if check !== 0}
    <p class="warn">
      Assets and liabilities plus equity differ by {(check / 100).toFixed(2)}.
      This usually means amounts in another currency without a price.
    </p>
  {/if}
</ReportFrame>

<style>
  .muted {
    color: var(--qb-muted);
  }

  .opt {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }

  .warn {
    margin: 1rem 0 0;
    color: var(--warning);
  }
</style>
