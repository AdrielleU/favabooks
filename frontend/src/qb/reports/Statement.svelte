<!--
  qb-fork: a financial statement table: account trees with subtotals per
  section, computed lines, and amounts that drill down to transactions.
-->
<script lang="ts">
  import type { QbStatement } from "../api.ts";
  import { money } from "../format.ts";
  import { line_row, pct_change, tree_rows } from "./helpers.ts";

  let {
    statement,
    collapsed,
    ontoggle,
    drill,
    show_change = false,
  }: {
    statement: QbStatement;
    collapsed: ReadonlySet<string>;
    ontoggle: (account: string) => void;
    /** Link to the transactions behind an account's amount in a column. */
    drill: (account: string, column: number) => string;
    /** Add a % change column (current vs previous). */
    show_change?: boolean;
  } = $props();

  let rows = $derived(
    statement.blocks.flatMap((block) =>
      block.kind === "section"
        ? tree_rows(block.title, block.node, collapsed, block.amounts)
        : [line_row(block.key, block.title, block.amounts)],
    ),
  );

  const fmt = (n: number) => money(n, statement.currency);
  const change = (amounts: number[]) => {
    const pct = pct_change(amounts[0] ?? 0, amounts[1] ?? 0);
    return pct === null ? "" : `${pct.toFixed(1)}%`;
  };
</script>

<table>
  <thead>
    <tr>
      <th></th>
      {#each statement.columns as column (column.label)}
        <th class="num">{column.label}</th>
      {/each}
      {#if show_change}<th class="num">% change</th>{/if}
    </tr>
  </thead>
  <tbody>
    {#each rows as row (row.key)}
      <tr class={row.kind}>
        <td style:padding-left={`${(row.depth * 1.2 + 0.5).toString()}rem`}>
          {#if row.collapsible}
            <button
              type="button"
              class="toggle"
              aria-expanded={!row.collapsed}
              onclick={() => {
                ontoggle(row.account);
              }}>{row.collapsed ? "▸" : "▾"}</button
            >
          {/if}
          {row.label}
        </td>
        {#each row.amounts as n, i (i)}
          <td class="num" class:negative={row.kind === "line" && n < 0}>
            {#if row.account && n !== 0}
              <a href={drill(row.account, i)} title="Show transactions"
                >{fmt(n)}</a
              >
            {:else if row.kind === "total" || row.kind === "line" || n !== 0}
              {fmt(n)}
            {/if}
          </td>
        {:else}
          {#each statement.columns as column (column.label)}<td></td>{/each}
        {/each}
        {#if show_change}
          <td class="num">{row.amounts.length ? change(row.amounts) : ""}</td>
        {/if}
      </tr>
    {/each}
  </tbody>
</table>

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
  }

  th {
    font-size: 0.85em;
    font-weight: 600;
    color: var(--text-color-lighter);
    border-bottom: 1px solid var(--border-darker);
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

  .section td {
    padding-top: 1em;
    font-weight: 700;
  }

  .group td {
    font-weight: 600;
  }

  .total td {
    font-weight: 600;
    border-top: 1px solid var(--border);
  }

  .line td {
    padding: 0.6em;
    font-weight: 700;
    border-top: 1px solid var(--border-darker);
    border-bottom: 3px double var(--border-darker);
  }

  .negative {
    color: var(--error);
  }

  .toggle {
    width: 1.2em;
    padding: 0;
    margin-left: -1.2em;
    color: var(--qb-muted);
    background: none;
  }
</style>
