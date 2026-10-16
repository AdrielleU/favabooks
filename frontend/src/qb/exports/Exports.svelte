<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import { HAVE_EXCEL } from "../../stores/index.ts";
  import type { QbExports } from "../api.ts";

  let { data }: { data: QbExports } = $props();

  // Only years the books have transactions in, newest first.
  let year = $derived(data.year);
  let exports = $derived(data.exports);
  let years = $derived(
    data.years.includes(year) || data.years.length === 0
      ? data.years
      : [year, ...data.years].toSorted((a, b) => b - a),
  );

  function pick_year(event: Event) {
    const url = new URL(window.location.href);
    url.searchParams.set(
      "year",
      (event.currentTarget as HTMLSelectElement).value,
    );
    router.navigate(url);
  }
</script>

{#if data.years.length === 0}
  <p class="hint">No transactions yet: import some first.</p>
{/if}

<div class="head">
  <label>
    Year
    <select value={year} onchange={pick_year}>
      {#each years as y (y)}
        <option value={y}>{y}</option>
      {/each}
    </select>
  </label>
  <p class="hint">
    The CPA package: download each report for the year. Dates are built into
    each report, so the header filters don't apply here.
  </p>
</div>

<div class="grid">
  {#each exports as item (item.key)}
    <section class="qb-card">
      <h3>{item.title}</h3>
      <p>{item.description}</p>
      <div class="links">
        <a
          class="button"
          href={$url_for("download-query/query_result.csv", {
            query_string: item.query,
          })}
          data-remote
        >
          CSV
        </a>
        {#if $HAVE_EXCEL}
          <a
            class="button"
            href={$url_for("download-query/query_result.xlsx", {
              query_string: item.query,
            })}
            data-remote
          >
            XLSX
          </a>
        {/if}
        <a href={$url_for("query/", { query_string: item.query })}
          >Open in Query</a
        >
      </div>
    </section>
  {/each}
</div>

<style>
  .head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
    align-items: center;
    margin-bottom: 1rem;
  }

  .head label {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-weight: 500;
  }

  .hint,
  section p {
    margin: 0;
    color: var(--text-color-lightest);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 18rem), 1fr));
    gap: 1rem;
  }

  h3 {
    margin: 0 0 0.4rem;
    font-size: 1em;
    font-weight: 500;
  }

  .links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin-top: 0.9rem;
  }

  .links a.button {
    padding: 0.25em 0.9em;
    color: var(--button-color);
    background: var(--button-background);
    border-radius: 4px;
  }
</style>
