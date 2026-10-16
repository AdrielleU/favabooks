<!--
  qb-fork: QuickBooks-style top bar. Replaces the stock sidebar/Header.svelte
  (kept untouched for upstream merges): company name above a large page
  title, the stock filter form, and icon buttons for errors, settings, help.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { keyboardShortcut } from "../../keyboard-shortcuts.ts";
  import { router } from "../../router.ts";
  import AccountPageTitle from "../../sidebar/AccountPageTitle.svelte";
  import FilterForm from "../../sidebar/FilterForm.svelte";
  import HeaderIcon from "../../sidebar/HeaderIcon.svelte";
  import { has_changes, page_title } from "../../sidebar/page-title.ts";
  import { errors, ledger_data } from "../../stores/index.ts";
  import { ledger_title } from "../../stores/options.ts";
  import Icon from "../Icon.svelte";

  /** Stock page titles renamed to match the nav. */
  const TITLES: Record<string, string> = {
    "Income Statement": "Profit and loss",
    Journal: "All transactions",
    Import: "Import files",
    "Help - Index": "Help",
  };

  let other_ledgers = $derived($ledger_data.other_ledgers);
  let { title: raw_title, type } = $derived($page_title);
  let title = $derived(TITLES[raw_title] ?? raw_title);
</script>

<header>
  <HeaderIcon />
  <div class="titles">
    <div class="company" class:switcher={other_ledgers.length > 0}>
      <Icon name="building" size={14} />
      <span>{$ledger_title}</span>
      {#if other_ledgers.length}
        <Icon name="chevron-down" size={14} />
        <ul class="ledgers">
          {#each other_ledgers as [name, url] (url)}
            <li><a href={url} data-remote>{name}</a></li>
          {/each}
        </ul>
      {/if}
    </div>
    <h1>
      {#if type === "account"}
        <AccountPageTitle account={title} />
      {:else}
        {title}
      {/if}
    </h1>
  </div>
  <button
    type="button"
    hidden={!$has_changes}
    class="reload-page"
    title="The ledger changed on disk: reload"
    {@attach keyboardShortcut("r")}
    onclick={router.reload}
  >
    Reload
  </button>
  <span class="spacer"></span>
  <FilterForm />
  <nav class="tools" aria-label="Tools">
    <a
      href={$url_for("errors/")}
      class="tool"
      title={$errors.length
        ? `${$errors.length.toString()} ledger errors`
        : "No ledger errors"}
    >
      <Icon name="bell" />
      {#if $errors.length}<span class="badge">{$errors.length}</span>{/if}
    </a>
    <a href={$url_for("options/")} class="tool" title="Settings">
      <Icon name="settings" />
    </a>
    <a href={$url_for("help/")} class="tool" title="Help">
      <Icon name="circle-question-mark" />
    </a>
  </nav>
</header>

<style>
  header {
    min-height: 64px;
    padding: 0.5rem 1rem;
  }

  .titles {
    display: flex;
    flex-direction: column;
    min-width: 0;
    line-height: 1.2;
  }

  .company {
    position: relative;
    display: flex;
    gap: 0.3rem;
    align-items: center;
    font-size: 0.8rem;
    color: var(--qb-muted);
  }

  .company.switcher {
    cursor: pointer;
  }

  .ledgers {
    position: absolute;
    top: 100%;
    left: 0;
    z-index: var(--z-index-floating-ui);
    display: none;
    min-width: 16rem;
    max-height: 400px;
    padding: 0.4rem 0;
    margin: 0;
    overflow-y: auto;
    list-style: none;
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--qb-shadow-lg);
  }

  .company:hover .ledgers {
    display: block;
  }

  .ledgers a {
    display: block;
    padding: 0.45rem 1rem;
    font-size: 0.9rem;
    color: var(--text-color);
  }

  .ledgers a:hover {
    background: var(--background-darker);
  }

  h1 {
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 1.35rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .reload-page {
    padding: 0.3rem 0.9rem;
    color: var(--dark-gray);
    background-color: var(--warning);
  }

  .tools {
    display: flex;
    gap: 0.25rem;
    align-items: center;
    margin-left: 0.5rem;
  }

  .tool {
    position: relative;
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    color: var(--qb-muted);
    border-radius: 50%;
  }

  .tool:hover {
    color: var(--header-color);
    background: var(--background-darker);
  }

  .badge {
    position: absolute;
    top: 2px;
    right: 1px;
    min-width: 16px;
    padding: 0 4px;
    font-size: 10px;
    font-weight: 600;
    line-height: 16px;
    color: #fff;
    text-align: center;
    background: var(--error);
    border-radius: 8px;
  }

  @media (width <= 767px) {
    h1 {
      font-size: 1.1rem;
    }

    .tools {
      display: none;
    }
  }
</style>
