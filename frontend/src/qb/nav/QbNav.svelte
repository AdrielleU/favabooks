<!--
  qb-fork: QuickBooks-style left nav. Replaces the stock
  sidebar/AsideContents.svelte (kept untouched for upstream merges) and keeps
  every stock page, keyboard shortcut, saved query and extension reachable.
  Groups collapse; their state is remembered per browser.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { _ } from "../../i18n.ts";
  import {
    keyboardShortcut,
    show_keyboard_shortcuts,
  } from "../../keyboard-shortcuts.ts";
  import AccountSelector from "../../sidebar/AccountSelector.svelte";
  import { errors, extensions, ledger_data } from "../../stores/index.ts";
  import { pathname } from "../../stores/url.ts";
  import Icon from "../Icon.svelte";
  import QbGroup from "./QbGroup.svelte";
  import QbLink from "./QbLink.svelte";

  const truncate = (s: string) => (s.length <= 25 ? s : `${s.slice(0, 24)}…`);

  let user_queries = $derived($ledger_data.user_queries);
  let upcoming_events_count = $derived($ledger_data.upcoming_events_count);
  let sidebar_links = $derived($ledger_data.sidebar_links);
  let extension_reports = $derived(
    $extensions.filter((e) => e.report_title != null),
  );

  /** Pages in each group, to keep the current page's group open. */
  const GROUP_PAGES: Record<string, string[]> = {
    banking: ["qb_review", "import", "qb_banks", "qb_reconcile"],
    transactions: ["qb_transactions", "qb_register", "qb_reclassify"],
    sales: ["qb_customers", "qb_invoices"],
    expenses: ["qb_vendors", "qb_bills"],
    reports: [
      "income_statement",
      "balance_sheet",
      "trial_balance",
      "query",
      "qb_exports",
    ],
    accounting: ["account", "documents", "editor"],
    advanced: ["journal", "holdings", "commodities", "events", "statistics"],
    settings: ["options", "errors", "qb_close_books", "help"],
  };
  const STORAGE_KEY = "favabooks-nav-open";

  /** Groups the user opened; the current page's group is always open. */
  function load_open(): Record<string, boolean> {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw === null ? {} : (JSON.parse(raw) as Record<string, boolean>);
    } catch {
      return {};
    }
  }

  let opened = $state(load_open());
  let current_report = $derived($pathname.split("/").filter(Boolean)[1] ?? "");

  function is_current(group: string): boolean {
    return (GROUP_PAGES[group] ?? []).includes(current_report);
  }

  function is_open(group: string): boolean {
    return opened[group] === true || is_current(group);
  }

  function toggle(group: string) {
    opened[group] = !is_open(group);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(opened));
    } catch {
      // Storage can be unavailable (private windows); collapsing still works.
    }
  }

  let new_menu_open = $state(false);
</script>

<!-- Always present, so the "n" shortcut works with the menu closed. -->
<a
  href="#add-transaction"
  class="shortcut-only"
  {@attach keyboardShortcut("n")}
>
  Add transaction
</a>

<div class="new">
  <button
    type="button"
    class="new-button"
    aria-expanded={new_menu_open}
    onclick={() => (new_menu_open = !new_menu_open)}
  >
    <Icon name="plus" />
    New
  </button>
  {#if new_menu_open}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="new-menu" onclick={() => (new_menu_open = false)}>
      <a href="#add-transaction">
        <Icon name="arrow-left-right" />Transaction or expense
      </a>
      <a href={$url_for("import/")}><Icon name="upload" />Import bank file</a>
      <a href={$url_for("qb_review/")}><Icon name="inbox" />Review imports</a>
      <a href={$url_for("qb_banks/")}
        ><Icon name="landmark" />Add a bank or card account</a
      >
      <a href={$url_for("documents/")}><Icon name="folder" />Upload a receipt</a
      >
    </div>
  {/if}
</div>

{#if sidebar_links.length}
  <ul class="navigation">
    {#each sidebar_links as [label, link] (link)}
      <QbLink report={link} name={label} remote />
    {/each}
  </ul>
{/if}

<ul class="navigation top">
  <QbLink report="qb_dashboard" name="Dashboard" icon="house" />
</ul>

<QbGroup
  label="Banking"
  icon="landmark"
  open={is_open("banking")}
  current={is_current("banking")}
  ontoggle={() => {
    toggle("banking");
  }}
/>
{#if is_open("banking")}
  <ul class="navigation">
    <QbLink report="qb_review" name="For review" />
    <QbLink report="import" name="Import files" key="g n">
      <a href="#export" class="secondary" title={_("Export")}>
        <Icon name="download" size={15} />
      </a>
    </QbLink>
    <QbLink report="qb_banks" name="Bank & card accounts" />
    <QbLink report="qb_reconcile" name="Reconcile" />
  </ul>
{/if}

<QbGroup
  label="Transactions"
  icon="arrow-left-right"
  open={is_open("transactions")}
  current={is_current("transactions")}
  ontoggle={() => {
    toggle("transactions");
  }}
/>
{#if is_open("transactions")}
  <ul class="navigation">
    <QbLink report="qb_transactions" name="All transactions" />
    <QbLink report="qb_register" name="Register" />
    <QbLink report="qb_reclassify" name="Bulk reclassify" />
  </ul>
{/if}

<QbGroup
  label="Sales"
  icon="receipt"
  open={is_open("sales")}
  current={is_current("sales")}
  ontoggle={() => {
    toggle("sales");
  }}
/>
{#if is_open("sales")}
  <ul class="navigation">
    <QbLink report="qb_customers" name="Customers" soon />
    <QbLink report="qb_invoices" name="Invoices" soon />
  </ul>
{/if}

<QbGroup
  label="Expenses"
  icon="wallet"
  open={is_open("expenses")}
  current={is_current("expenses")}
  ontoggle={() => {
    toggle("expenses");
  }}
/>
{#if is_open("expenses")}
  <ul class="navigation">
    <QbLink report="qb_vendors" name="Vendors" soon />
    <QbLink report="qb_bills" name="Bills" soon />
  </ul>
{/if}

<QbGroup
  label="Reports"
  icon="chart-column"
  open={is_open("reports")}
  current={is_current("reports")}
  ontoggle={() => {
    toggle("reports");
  }}
/>
{#if is_open("reports")}
  <ul class="navigation">
    <QbLink report="income_statement" name="Profit and loss" key="g i" />
    <QbLink report="balance_sheet" name={_("Balance Sheet")} key="g b" />
    <QbLink report="trial_balance" name={_("Trial Balance")} key="g t" />
    <QbLink report="query" name={_("Query")} key="g q">
      {#if user_queries.length}
        <ul class="submenu">
          {#each user_queries as { query_string, name } (query_string)}
            <li>
              <a href={$url_for("query/", { query_string })}>{truncate(name)}</a
              >
            </li>
          {/each}
        </ul>
      {/if}
    </QbLink>
    <QbLink report="qb_exports" name="Export for CPA" />
  </ul>
{/if}

<QbGroup
  label="Accounting"
  icon="calculator"
  open={is_open("accounting")}
  current={is_current("accounting")}
  ontoggle={() => {
    toggle("accounting");
  }}
/>
{#if is_open("accounting")}
  <ul class="navigation">
    <AccountSelector />
    <QbLink report="documents" name={_("Documents")} key="g d" />
    <QbLink report="editor" name={_("Editor")} key="g e" />
  </ul>
{/if}

<QbGroup
  label="Advanced"
  icon="sliders-horizontal"
  open={is_open("advanced")}
  current={is_current("advanced")}
  ontoggle={() => {
    toggle("advanced");
  }}
/>
{#if is_open("advanced")}
  <ul class="navigation">
    <QbLink report="journal" name="Journal" key="g j" />
    <QbLink report="holdings" name={_("Holdings")} key="g h" />
    <QbLink report="commodities" name={_("Commodities")} key="g c" />
    <QbLink
      report="events"
      name={_("Events")}
      key="g E"
      bubble={[upcoming_events_count, "info"]}
    />
    <QbLink report="statistics" name={_("Statistics")} key="g s" />
  </ul>
{/if}

<QbGroup
  label="Settings"
  icon="settings"
  open={is_open("settings")}
  current={is_current("settings")}
  ontoggle={() => {
    toggle("settings");
  }}
/>
{#if is_open("settings")}
  <ul class="navigation">
    <QbLink report="options" name={_("Options")} key="g o" />
    {#if $errors.length > 0}
      <QbLink
        report="errors"
        name={_("Errors")}
        bubble={[$errors.length, "error"]}
      />
    {/if}
    <QbLink report="qb_close_books" name="Close books" soon />
    <QbLink report="help" name={_("Help")} key="g H">
      <button
        type="button"
        class="secondary link"
        title={_("Show keyboard shortcuts")}
        onclick={show_keyboard_shortcuts}
        {@attach keyboardShortcut("?")}
      >
        ?
      </button>
    </QbLink>
  </ul>
{/if}

{#if extension_reports.length}
  <ul class="navigation">
    {#each extension_reports as ext (ext.name)}
      <QbLink report={`extension/${ext.name}`} name={ext.report_title ?? ""} />
    {/each}
  </ul>
{/if}

<style>
  .shortcut-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .new {
    position: relative;
    padding: 0.75rem 0.75rem 0.5rem;
  }

  .new-button {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 0.55rem 1rem;
    font-size: 0.95rem;
    font-weight: 600;
    color: #fff;
    background: var(--qb-accent-strong);
    border-radius: 999px;
  }

  .new-button:hover {
    filter: brightness(1.08);
  }

  .new-menu {
    position: absolute;
    top: calc(100% - 0.25rem);
    right: 0.75rem;
    left: 0.75rem;
    z-index: var(--z-index-floating-ui);
    padding: 0.4rem;
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--qb-shadow-lg);
  }

  .new-menu a {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    padding: 0.5rem 0.6rem;
    font-size: 0.9rem;
    color: var(--text-color);
    border-radius: 6px;
  }

  .new-menu a:hover {
    background: var(--background-darker);
  }

  .navigation {
    padding: 0 0.5rem 0.35rem;
    margin: 0;
  }

  .navigation.top {
    padding-top: 0.25rem;
  }

  /* Trailing buttons float over the row so its highlight stays full width. */
  .secondary {
    position: absolute;
    top: 2px;
    right: 0.35rem;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    padding: 0;
    color: inherit;
    background: none;
    border-radius: 6px;
  }

  .secondary:hover {
    background: var(--sidebar-border);
  }

  /* "Go to account": an outlined search box, not a selected-looking slab. */
  .navigation :global(input) {
    margin: 0.2rem 0 0.3rem;
    color: var(--sidebar-color);
    background: transparent;
    border: 1px solid var(--qb-nav-raised);
    border-radius: 6px;
  }

  .navigation :global(input:focus) {
    border-color: var(--sidebar-color);
  }

  .submenu {
    width: 100%;
    margin: 0 0 0.3rem;
  }

  .submenu a {
    display: block;
    padding: 0.2rem 0.5rem 0.2rem 3.2rem;
    font-size: 0.88em;
    color: inherit;
    opacity: 0.85;
  }

  .submenu a:hover {
    opacity: 1;
  }
</style>
