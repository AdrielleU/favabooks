<!--
  qb-fork: the date filter for Invoices/Bills and Customers/Vendors: quick
  presets, years and months that have data, or a custom range. Kept in the
  URL as period (and from/to for a custom range).
-->
<script lang="ts">
  import { router } from "../../router.ts";
  import Icon from "../Icon.svelte";
  import type { Period } from "./periods.ts";
  import { data_months, data_years, presets } from "./periods.ts";

  let {
    period,
    today,
    dates,
  }: {
    /** The selected period. */
    period: Period;
    today: Date;
    /** Dates that have data (for the year and month lists). */
    dates: readonly Date[];
  } = $props();

  let quick = $derived(presets(today));
  let years = $derived(data_years(dates));
  let months = $derived(data_months(dates));
  let custom = $derived(period.key === "custom");
  let from = $derived(period.start);
  let to = $derived(period.end);

  function go(params: Record<string, string>) {
    const url = new URL(window.location.href);
    for (const name of ["period", "from", "to"]) {
      url.searchParams.delete(name);
    }
    for (const [name, value] of Object.entries(params)) {
      if (value && !(name === "period" && value === "all")) {
        url.searchParams.set(name, value);
      }
    }
    router.navigate(url);
  }
</script>

<div class="picker">
  <Icon name="calendar" size={16} />
  <select
    aria-label="Dates"
    value={period.key}
    onchange={(e) => {
      const key = e.currentTarget.value;
      if (key === "custom") {
        go({ period: "custom", from: period.start, to: period.end });
      } else {
        go({ period: key });
      }
    }}
  >
    <optgroup label="Dates">
      {#each quick as p (p.key)}<option value={p.key}>{p.label}</option>{/each}
      <option value="custom">Custom range…</option>
    </optgroup>
    {#if years.length}
      <optgroup label="Years">
        {#each years as p (p.key)}<option value={p.key}>{p.label}</option
          >{/each}
      </optgroup>
    {/if}
    {#if months.length}
      <optgroup label="Months">
        {#each months as p (p.key)}<option value={p.key}>{p.label}</option
          >{/each}
      </optgroup>
    {/if}
  </select>
  {#if custom}
    <form
      class="custom"
      onsubmit={(e) => {
        e.preventDefault();
        go({ period: "custom", from, to });
      }}
    >
      <input type="date" aria-label="From" bind:value={from} />
      <span>to</span>
      <input type="date" aria-label="To" bind:value={to} />
      <button type="submit" class="qb-secondary small">Apply</button>
    </form>
  {/if}
</div>

<style>
  .picker {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
    color: var(--qb-muted);
  }

  select {
    color: var(--text-color);
  }

  .custom {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
  }

  .small {
    padding: 0.3em 0.9em;
    font-size: 0.88em;
  }
</style>
