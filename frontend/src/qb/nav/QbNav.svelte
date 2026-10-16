<!--
  qb-fork: QuickBooks-style grouped left nav. Replaces the stock
  sidebar/AsideContents.svelte (kept untouched for upstream merges) and keeps
  every stock page, keyboard shortcut and extension link reachable.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { _ } from "../../i18n.ts";
  import {
    keyboardShortcut,
    show_keyboard_shortcuts,
  } from "../../keyboard-shortcuts.ts";
  import AccountSelector from "../../sidebar/AccountSelector.svelte";
  import Link from "../../sidebar/SidebarLink.svelte";
  import { errors, extensions, ledger_data } from "../../stores/index.ts";

  const truncate = (s: string) => (s.length <= 25 ? s : `${s.slice(0, 24)}…`);

  let user_queries = $derived($ledger_data.user_queries);
  let upcoming_events_count = $derived($ledger_data.upcoming_events_count);
  let sidebar_links = $derived($ledger_data.sidebar_links);
  let extension_reports = $derived(
    $extensions.filter((e) => e.report_title != null),
  );
</script>

{#if sidebar_links.length}
  <ul class="navigation">
    {#each sidebar_links as [label, link] (link)}
      <Link report={link} name={label} remote />
    {/each}
  </ul>
{/if}
<ul class="navigation">
  <Link report="qb_dashboard" name="Dashboard" />
</ul>

<h3>Banking</h3>
<ul class="navigation">
  <Link report="qb_review" name="For review" />
  <Link report="import" name="Import files" key="g n">
    <a href="#export" class="secondary" title={_("Export")}>⬇</a>
  </Link>
  <Link report="qb_reconcile" name="Reconcile (WIP)" />
</ul>

<h3>Transactions</h3>
<ul class="navigation">
  <Link report="journal" name="All transactions" key="g j" />
  <Link report="qb_register" name="Register" />
  <Link report="qb_reclassify" name="Bulk reclassify" />
</ul>

<h3>Sales</h3>
<ul class="navigation">
  <Link report="qb_customers" name="Customers (WIP)" />
  <Link report="qb_invoices" name="Invoices (WIP)" />
</ul>

<h3>Expenses</h3>
<ul class="navigation">
  <Link report="qb_vendors" name="Vendors (WIP)" />
  <Link report="qb_bills" name="Bills (WIP)" />
</ul>

<h3>Reports</h3>
<ul class="navigation">
  <Link report="income_statement" name="Profit and loss" key="g i" />
  <Link report="balance_sheet" name={_("Balance Sheet")} key="g b" />
  <Link report="trial_balance" name={_("Trial Balance")} key="g t" />
  <Link report="query" name={_("Query")} key="g q">
    {#if user_queries.length}
      <ul class="submenu">
        {#each user_queries as { query_string, name } (query_string)}
          <li>
            <a href={$url_for("query/", { query_string })}>{truncate(name)}</a>
          </li>
        {/each}
      </ul>
    {/if}
  </Link>
  <Link report="qb_exports" name="Export for CPA" />
</ul>

<h3>Accounting</h3>
<ul class="navigation">
  <AccountSelector />
  <Link report="documents" name={_("Documents")} key="g d" />
  <Link report="editor" name={_("Editor")} key="g e">
    <a
      href="#add-transaction"
      class="secondary add-transaction"
      title={_("Add Journal Entry")}
      {@attach keyboardShortcut("n")}
    >
      +
    </a>
  </Link>
  <Link report="holdings" name={_("Holdings")} key="g h" />
  <Link report="commodities" name={_("Commodities")} key="g c" />
  <Link
    report="events"
    name={_("Events")}
    key="g E"
    bubble={[upcoming_events_count, "info"]}
  />
  <Link report="statistics" name={_("Statistics")} key="g s" />
</ul>

<h3>Settings</h3>
<ul class="navigation">
  <Link report="options" name={_("Options")} key="g o" />
  {#if $errors.length > 0}
    <Link
      report="errors"
      name={_("Errors")}
      bubble={[$errors.length, "error"]}
    />
  {/if}
  <Link report="qb_close_books" name="Close books (WIP)" />
  <Link report="help" name={_("Help")} key="g H">
    <button
      type="button"
      class="secondary link"
      title={_("Show keyboard shortcuts")}
      onclick={show_keyboard_shortcuts}
      {@attach keyboardShortcut("?")}
    >
      ?
    </button>
  </Link>
</ul>
{#if extension_reports.length}
  <h3>Extensions</h3>
  <ul class="navigation">
    {#each extension_reports as ext (ext.name)}
      <Link report={`extension/${ext.name}`} name={ext.report_title ?? ""} />
    {/each}
  </ul>
{/if}

<style>
  h3 {
    padding: 0.9rem 1rem 0.25rem;
    margin: 0;
    font-size: 0.72em;
    font-weight: 500;
    color: hsl(220deg 9% 65%);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .navigation {
    margin: 0;
  }

  a {
    display: block;
    padding: 0.25em 0.5em 0.25em 1em;
    color: inherit;
  }

  a:hover {
    color: var(--sidebar-hover-color);
    background-color: var(--sidebar-border);
  }

  .secondary {
    width: 30px;
    padding: 3px 9px;
    line-height: 22px;
    color: inherit;
    background-color: var(--sidebar-background);
  }

  .add-transaction {
    font-size: 23px;
  }

  .submenu {
    width: 100%;
    margin: 0 0 0.5em;
  }

  .submenu a {
    width: 100%;
    padding-left: 35px;
  }

  .submenu li {
    font-size: 0.9em;
  }
</style>
