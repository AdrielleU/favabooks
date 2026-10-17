<!-- qb-fork: Balance sheet, QuickBooks style. -->
<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";

  import { url_for } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import type { QbStatement } from "../api.ts";
  import { iso, to_csv } from "../docs/periods.ts";
  import AsOfPicker from "./AsOfPicker.svelte";
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
    today,
    compare,
  }: { statement: QbStatement; today: Date; compare: boolean } = $props();

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
