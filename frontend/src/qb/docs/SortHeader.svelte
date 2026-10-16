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
