<!-- qb-fork: Profit and loss, QuickBooks style. -->
<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";

  import { url_for } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import { years } from "../../stores/index.ts";
  import type { QbStatement } from "../api.ts";
  import PeriodPicker from "../docs/PeriodPicker.svelte";
  import type { Period } from "../docs/periods.ts";
  import { iso, to_csv } from "../docs/periods.ts";
  import { download_csv } from "./download.ts";
  import {
    date_range_label,
    line_row,
    months_of_years,
    parents,
    statement_rows,
    tree_rows,
  } from "./helpers.ts";
  import ReportFrame from "./ReportFrame.svelte";
  import Statement from "./Statement.svelte";

  let {
    statement,
    period,
    today,
    by,
    compare,
  }: {
    statement: QbStatement;
    period: Period;
    today: Date;
    by: string;
    compare: boolean;
  } = $props();

  const collapsed = new SvelteSet<string>();
  let total = $derived(
    statement.columns.find((c) => c.label === "Total") ?? statement.columns[0],
  );
  let subtitle = $derived(
    total ? date_range_label(total.start, total.end) : "",
  );

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
      from: column?.start ? iso(column.start) : "",
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
      `profit-and-loss-${period.key}.csv`,
    );
  }
</script>

<ReportFrame
  company={statement.company}
  title="Profit and loss"
  {subtitle}
  unconverted={statement.unconverted}
  onexport={export_csv}
  onexpand={() => {
    collapsed.clear();
  }}
  oncollapse={() => {
    collapse_all(statement.blocks.flatMap((b) => parents(b.node)));
  }}
>
  {#snippet options()}
    <PeriodPicker {period} {today} dates={months_of_years($years, today)} />
    <label class="opt">
      Columns
      <select
        value={by}
        onchange={(e) => {
          go({
            by: e.currentTarget.value === "total" ? "" : e.currentTarget.value,
            compare: "",
          });
        }}
      >
        <option value="total">Total only</option>
        <option value="month">Months</option>
        <option value="quarter">Quarters</option>
        <option value="year">Years</option>
      </select>
    </label>
    {#if by === "total"}
      <label class="opt">
        <input
          type="checkbox"
          checked={compare}
          onchange={(e) => {
            go({ compare: e.currentTarget.checked ? "1" : "" });
          }}
        />
        Compare with previous period
      </label>
    {/if}
  {/snippet}
  <Statement
    {statement}
    {collapsed}
    ontoggle={toggle}
    {drill}
    show_change={compare && by === "total"}
  />
</ReportFrame>

<style>
  .opt {
    display: flex;
    gap: 0.4rem;
    align-items: center;
  }
</style>
