<!--
  qb-fork: the KPI cards and charts above a report (laid out in a grid).
-->
<script lang="ts">
  import type { Snippet } from "svelte";

  export interface Kpi {
    label: string;
    value: string;
    /** "+12.5% vs previous period", or "". */
    change: string;
    /** Whether the change is good news (green) or not (red). */
    good: boolean | null;
  }

  let {
    kpis,
    trend_title,
    trend,
    side_title = "",
    side,
  }: {
    kpis: Kpi[];
    trend_title: string;
    trend: Snippet;
    side_title?: string;
    side?: Snippet;
  } = $props();
</script>

<div class="kpis">
  {#each kpis as k (k.label)}
    <div class="qb-card kpi">
      <span class="label">{k.label}</span>
      <strong>{k.value}</strong>
      {#if k.change}
        <span
          class="change"
          class:good={k.good === true}
          class:bad={k.good === false}>{k.change}</span
        >
      {/if}
    </div>
  {/each}
</div>
<div class="grid" class:single={!side}>
  <div class="qb-card panel">
    <h3>{trend_title}</h3>
    {@render trend()}
  </div>
  {#if side}
    <div class="qb-card panel">
      <h3>{side_title}</h3>
      {@render side()}
    </div>
  {/if}
</div>

<style>
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
    gap: 0.8rem;
    margin-bottom: 0.8rem;
  }

  .kpi {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .label {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .kpi strong {
    font-size: 1.35rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .change {
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .change.good {
    color: var(--qb-accent);
  }

  .change.bad {
    color: var(--error);
  }

  .grid {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
    gap: 0.8rem;
  }

  .grid.single {
    grid-template-columns: minmax(0, 1fr);
  }

  @media (width <= 900px) {
    .grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  h3 {
    margin: 0 0 0.6rem;
    font-size: 0.95rem;
  }
</style>
