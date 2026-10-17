<!--
  qb-fork: "As of" date for the balance sheet and trial balance: quick
  choices (today, end of last month/quarter/year, year ends) or a date.
-->
<script lang="ts">
  import { router } from "../../router.ts";
  import { years } from "../../stores/index.ts";
  import Icon from "../Icon.svelte";
  import { as_of_choices } from "./helpers.ts";

  let { value, today }: { value: string; today: Date } = $props();

  let choices = $derived(
    as_of_choices(
      today,
      $years.map(Number).filter((y) => y < today.getUTCFullYear()),
    ),
  );
  let picked = $derived(choices.find((c) => c.date === value)?.date ?? "");

  function go(as_of: string) {
    const url = new URL(window.location.href);
    if (as_of) {
      url.searchParams.set("as_of", as_of);
    } else {
      url.searchParams.delete("as_of");
    }
    router.navigate(url);
  }
</script>

<label class="as-of">
  <Icon name="calendar" size={16} />
  <span>As of</span>
  <select
    value={picked}
    onchange={(e) => {
      if (e.currentTarget.value) {
        go(e.currentTarget.value);
      }
    }}
  >
    {#if !picked}<option value="">Custom date</option>{/if}
    {#each choices as c (c.key)}
      <option value={c.date}>{c.label}</option>
    {/each}
  </select>
  <input
    type="date"
    aria-label="As of date"
    {value}
    onchange={(e) => {
      go(e.currentTarget.value);
    }}
  />
</label>

<style>
  .as-of {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
    color: var(--qb-muted);
  }

  .as-of span {
    color: var(--text-color);
  }
</style>
