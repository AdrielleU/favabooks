<!--
  qb-fork: a nav link like sidebar/SidebarLink.svelte, with an optional icon.
-->
<script lang="ts">
  import type { Snippet } from "svelte";

  import { url_for } from "../../helpers.ts";
  import type { KeySpec } from "../../keyboard-shortcuts.ts";
  import { keyboardShortcut } from "../../keyboard-shortcuts.ts";
  import { pathname } from "../../stores/url.ts";
  import Icon from "../Icon.svelte";
  import type { IconName } from "../icons.ts";

  interface Props {
    report: string;
    name: string;
    icon?: IconName;
    key?: KeySpec;
    remote?: true;
    bubble?: [number, "error" | "info"];
    /** Not built yet: shows a "Soon" chip. */
    soon?: boolean;
    children?: Snippet;
  }

  let { report, name, icon, key, remote, bubble, soon, children }: Props =
    $props();

  let href = $derived(remote ? report : $url_for(`${report}/`));
  let selected = $derived(remote ? false : href.includes($pathname));
</script>

<li>
  <a
    class:selected
    class:with-icon={icon}
    {href}
    {@attach keyboardShortcut(key)}
    data-remote={remote}
    aria-current={selected ? "page" : undefined}
  >
    {#if icon}<Icon name={icon} />{/if}
    <span class="name">{name}</span>
    {#if soon}<span class="soon">Soon</span>{/if}
    {#if bubble && bubble[0] > 0}
      <span class="bubble" class:error={bubble[1] === "error"}>{bubble[0]}</span
      >
    {/if}
  </a>
  {@render children?.()}
</li>

<style>
  li {
    position: relative;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
  }

  a {
    position: relative;
    display: flex;
    flex: 1;
    gap: 0.7rem;
    align-items: center;
    min-height: 34px;
    padding: 0.3rem 0.75rem 0.3rem 2.65rem;
    color: inherit;
    border-radius: 6px;
  }

  a.with-icon {
    padding-left: 0.85rem;
  }

  a:hover {
    color: var(--sidebar-hover-color);
    background: var(--sidebar-border);
  }

  a.selected {
    font-weight: 600;
    color: var(--sidebar-hover-color);
    background: var(--qb-nav-active);
  }

  a.selected::before {
    position: absolute;
    top: 6px;
    bottom: 6px;
    left: -0.5rem;
    width: 3px;
    content: "";
    background: var(--qb-accent-strong);
    border-radius: 0 3px 3px 0;
  }

  .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .soon {
    padding: 0 6px;
    font-size: 0.7em;
    font-weight: 600;
    line-height: 16px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    border: 1px solid currentcolor;
    border-radius: 8px;
    opacity: 0.6;
  }

  .bubble {
    min-width: 20px;
    padding: 0 6px;
    font-size: 0.75em;
    line-height: 18px;
    text-align: center;
    background: var(--sidebar-border);
    border-radius: 9px;
  }

  .bubble.error {
    color: white;
    background: var(--error);
  }
</style>
