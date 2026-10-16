<!--
  @component
  A Lucide icon (see icons.ts). Inherits the text colour; decorative unless
  a `label` is given.
-->
<script lang="ts">
  import { ICONS, type IconName } from "./icons.ts";

  interface Props {
    name: IconName;
    size?: number;
    label?: string;
  }

  let { name, size = 18, label }: Props = $props();
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden={label === undefined ? "true" : undefined}
  aria-label={label}
  role={label === undefined ? undefined : "img"}
>
  {#each ICONS[name] as [tag, attrs], i (i)}
    <svelte:element this={tag} {...attrs} />
  {/each}
</svg>

<style>
  svg {
    flex: none;
    vertical-align: middle;
  }
</style>
