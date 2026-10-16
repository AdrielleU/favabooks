<!-- qb-fork: a sortable table column header. -->
<script lang="ts">
  let {
    label,
    active,
    descending,
    num = false,
    onsort,
  }: {
    label: string;
    active: boolean;
    descending: boolean;
    num?: boolean;
    onsort: () => void;
  } = $props();
</script>

<th
  class:num
  aria-sort={active ? (descending ? "descending" : "ascending") : "none"}
>
  <button type="button" onclick={onsort}
    >{label}{active ? (descending ? " ↓" : " ↑") : ""}</button
  >
</th>

<style>
  /* Matches the th rules of the pages using it (styles are per component). */
  th {
    padding: 0.55em 0.75em;
    font-weight: 500;
    color: var(--text-color-lighter);
    text-align: left;
    white-space: nowrap;
    background: var(--background-darker);
    border: none;
    border-bottom: 1px solid var(--border);
  }

  .num {
    text-align: right;
  }

  button {
    padding: 0;
    font: inherit;
    color: inherit;
    background: none;
  }
</style>
