<!--
  qb-fork: the frame every report shares, like QuickBooks and Xero: a
  toolbar (report options on the left; expand/collapse, export and print on
  the right) and a report sheet headed by company, report name and dates.
-->
<script lang="ts">
  import type { Snippet } from "svelte";

  import Icon from "../Icon.svelte";

  let {
    company,
    title,
    subtitle,
    unconverted = [],
    options,
    onexport,
    onexpand,
    oncollapse,
    charts,
    children,
  }: {
    company: string;
    title: string;
    subtitle: string;
    unconverted?: string[];
    /** Report options (period, columns, compare). */
    options: Snippet;
    onexport: () => void;
    onexpand?: () => void;
    oncollapse?: () => void;
    /** KPI cards and charts shown above the report sheet. */
    charts?: Snippet;
    children: Snippet;
  } = $props();

  const KEY = "favabooks-report-charts";
  function load(): boolean {
    try {
      return localStorage.getItem(KEY) !== "hidden";
    } catch {
      return true;
    }
  }
  let show_charts = $state(load());
  function toggle_charts() {
    show_charts = !show_charts;
    try {
      localStorage.setItem(KEY, show_charts ? "shown" : "hidden");
    } catch {
      // Private mode: the choice just isn't remembered.
    }
  }
</script>

<div class="qb-card toolbar">
  <div class="options">{@render options()}</div>
  <div class="actions">
    {#if charts}
      <button type="button" class="link" onclick={toggle_charts}
        >{show_charts ? "Hide charts" : "Show charts"}</button
      >
    {/if}
    {#if onexpand && oncollapse}
      <button type="button" class="link" onclick={oncollapse}>Collapse</button>
      <button type="button" class="link" onclick={onexpand}>Expand</button>
    {/if}
    <button type="button" class="qb-secondary small" onclick={onexport}>
      <Icon name="download" size={15} /> Export CSV
    </button>
    <button
      type="button"
      class="qb-secondary small"
      onclick={() => {
        window.print();
      }}
    >
      <Icon name="printer" size={15} /> Print
    </button>
  </div>
</div>

{#if charts && show_charts}
  <div class="charts">{@render charts()}</div>
{/if}

<div class="qb-card sheet">
  <div class="sheet-head">
    <div class="company">{company}</div>
    <h2>{title}</h2>
    <div class="dates">{subtitle}</div>
  </div>
  {@render children()}
  {#if unconverted.length}
    <p class="note">
      Not included (no price to convert them): {unconverted.join(", ")}. Add
      price entries to include them.
    </p>
  {/if}
</div>

<style>
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1.5rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .options {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1.2rem;
    align-items: center;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.9rem;
    align-items: center;
  }

  .actions .small {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
    padding: 0.3em 0.9em;
    font-size: 0.88em;
  }

  .link {
    padding: 0;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }

  .charts {
    max-width: 64rem;
    margin: 0 auto 1rem;
  }

  .sheet {
    max-width: 64rem;
    padding: 1.5rem 1.5rem 2rem;
    margin: 0 auto;
    overflow-x: auto;
  }

  .sheet-head {
    margin-bottom: 1.2rem;
    text-align: center;
  }

  .company {
    font-weight: 600;
    color: var(--text-color-lighter);
  }

  h2 {
    margin: 0.2rem 0;
    font-size: 1.35rem;
  }

  .dates {
    color: var(--qb-muted);
  }

  .note {
    margin: 1rem 0 0;
    font-size: 0.85em;
    color: var(--warning);
  }

  @media print {
    .toolbar {
      display: none;
    }

    .sheet {
      max-width: none;
      box-shadow: none;
    }
  }
</style>
