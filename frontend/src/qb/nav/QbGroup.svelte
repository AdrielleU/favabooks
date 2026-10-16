<!--
  qb-fork: a collapsible nav group header (icon, label, chevron).
-->
<script lang="ts">
  import Icon from "../Icon.svelte";
  import type { IconName } from "../icons.ts";

  interface Props {
    label: string;
    icon: IconName;
    open: boolean;
    /** The current page is in this group. */
    current: boolean;
    ontoggle: () => void;
  }

  let { label, icon, open, current, ontoggle }: Props = $props();
</script>

<button
  type="button"
  class="group"
  class:current
  aria-expanded={open}
  onclick={ontoggle}
>
  <Icon name={icon} />
  <span>{label}</span>
  <Icon name={open ? "chevron-down" : "chevron-right"} size={16} />
</button>

<style>
  .group {
    display: flex;
    gap: 0.7rem;
    align-items: center;
    width: calc(100% - 1rem);
    min-height: 34px;
    padding: 0.3rem 0.75rem 0.3rem 0.85rem;
    margin: 0.15rem 0.5rem 0;
    font-size: 0.95em;
    font-weight: 600;
    color: inherit;
    text-align: left;
    background: none;
    border-radius: 6px;
  }

  .group span {
    flex: 1;
  }

  .group:hover,
  .group.current {
    color: var(--sidebar-hover-color);
  }

  .group:hover {
    background: var(--sidebar-border);
  }
</style>
