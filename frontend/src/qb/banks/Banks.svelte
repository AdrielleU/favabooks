<!--
  qb-fork: Bank & card accounts. Connect each account once (bank, ledger
  account, optional column mapping); files dropped in Import files are then
  recognised automatically.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import type { QbConnection, QbImportSetup } from "../api.ts";
  import { delete_qb_connection, put_qb_import_enable } from "../api.ts";
  import { short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import AddAccount from "./AddAccount.svelte";

  let { setup }: { setup: QbImportSetup } = $props();

  /** The open wizard: a new account, an edit, or one for an inbox file. */
  let wizard = $state<null | {
    editing: { connection: QbConnection; bank: string } | null;
    file: string | null;
  }>(null);
  /** Connection whose download instructions are shown. */
  let show_help = $state("");
  let busy = $state(false);

  let waiting = $derived(setup.inbox.filter((f) => f.importers.length === 0));
  let formats = $derived(
    new Map(
      setup.banks.flatMap((b) =>
        b.formats.map((f) => [f.key, { bank: b.bank, kind: f.kind }]),
      ),
    ),
  );

  async function enable() {
    busy = true;
    try {
      notify(await put_qb_import_enable());
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }

  async function remove(connection: QbConnection) {
    const label = connection.name || connection.account;
    if (
      !window.confirm(
        `Disconnect ${label}? Transactions already imported stay in your books.`,
      )
    ) {
      return;
    }
    try {
      await delete_qb_connection(connection.id);
      notify(`Disconnected ${label}.`);
      router.reload();
    } catch (error) {
      notify_err(error);
    }
  }

  function saved(name: string) {
    wizard = null;
    notify(`Saved. Files from ${name} will now be recognised in Import files.`);
    router.reload();
  }

  const initials = (text: string) =>
    text
      .split(/\s+/)
      .map((w) => w[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase();
</script>

<div class="page-head">
  <p class="muted">
    Tell Favabooks which file each account's statements come in. Once saved,
    files you drop in <a href={$url_for("import/")}>Import files</a> are recognised
    automatically.
  </p>
  {#if setup.status === "managed"}
    <button
      type="button"
      class="qb-primary add"
      onclick={() => (wizard = { editing: null, file: null })}
    >
      <Icon name="plus" size={16} /> Add account
    </button>
  {/if}
</div>

{#each setup.errors as error (error)}
  <p class="qb-card error">{error}</p>
{/each}

{#if setup.status !== "managed"}
  <section class="qb-card off">
    <span class="big-icon"><Icon name="landmark" size={28} /></span>
    <div>
      <h2>Turn on bank &amp; card imports</h2>
      {#if setup.status === "custom"}
        <p>
          This ledger has its own import config (<code>{setup.config_file}</code
          >). Turning this on adds one line to it so accounts you connect here
          are loaded as well; your existing importers keep working.
        </p>
      {:else}
        <p>
          Favabooks will create an <code>importers/</code> folder for your
          settings and an <code>inbox/</code> folder for statement files next to your
          ledger, and add two options to it.
        </p>
      {/if}
      <button type="button" class="qb-primary" disabled={busy} onclick={enable}>
        Turn on
      </button>
    </div>
  </section>
{:else if setup.connections.length === 0}
  <section class="qb-card empty">
    <span class="big-icon"><Icon name="landmark" size={28} /></span>
    <h2>No accounts yet</h2>
    <p class="muted">
      Add your first bank or credit card account. Have a statement file already?
      Start with it and Favabooks recognises the bank.
    </p>
    <button
      type="button"
      class="qb-primary"
      onclick={() => (wizard = { editing: null, file: null })}
    >
      <Icon name="plus" size={16} /> Add account
    </button>
  </section>
{:else}
  <div class="cards">
    {#each setup.connections as view (view.connection.id)}
      {@const c = view.connection}
      <div class="qb-card account">
        <div class="top">
          <span class="avatar">{initials(view.bank)}</span>
          <div class="title">
            <strong>{c.name || `${view.bank} ${view.kind_label}`}</strong>
            <span class="muted">{view.bank} · {view.kind_label}</span>
          </div>
        </div>
        <p class="posts">Posts to <code>{c.account}</code></p>
        <div class="chips">
          <span class="chip"
            >{c.kind === "custom"
              ? "Custom column mapping"
              : c.kind === "stripe"
                ? "Stripe payout report"
                : `${view.bank} CSV (built-in)`}</span
          >
          {#if c.filename}<span class="chip"
              >File name contains {c.filename}</span
            >{/if}
          {#if c.skip_stripe}<span class="chip">Leaves out Stripe payouts</span
            >{/if}
          {#if c.kind === "stripe"}<span class="chip"
              >Payouts to {c.payout_account}</span
            >{/if}
        </div>
        <p class="meta muted">
          {view.last_date
            ? `Last transaction ${short_date(view.last_date)}`
            : "No transactions yet"}
          · {view.documents} statement{view.documents === 1 ? "" : "s"} filed
        </p>
        {#if show_help === c.id}
          <p class="help">
            <Icon name="download" size={15} />
            {view.download ||
              "In online banking, look for Download or Export and choose CSV."}
          </p>
        {/if}
        <div class="actions">
          <a class="button qb-primary small" href={$url_for("import/")}
            >Import file</a
          >
          <button
            type="button"
            class="link"
            onclick={() => (show_help = show_help === c.id ? "" : c.id)}
          >
            How to download
          </button>
          <button
            type="button"
            class="link"
            onclick={() =>
              (wizard = {
                editing: { connection: c, bank: view.bank },
                file: null,
              })}
          >
            Edit
          </button>
          <button
            type="button"
            class="link danger"
            onclick={async () => remove(c)}>Disconnect</button
          >
        </div>
      </div>
    {/each}
  </div>
{/if}

{#if setup.status === "managed" && waiting.length}
  <section class="qb-card waiting">
    <h3>Files in Import files that no account recognises</h3>
    <ul>
      {#each waiting as f (f.filename)}
        {@const key = f.detected[0]}
        {@const guess = key === undefined ? undefined : formats.get(key)}
        <li>
          <Icon name="file-spreadsheet" size={16} />
          <span class="file">{f.basename}</span>
          <span class="muted"
            >{guess
              ? `Looks like ${guess.bank}, ${guess.kind}`
              : f.header.length
                ? "Unknown layout"
                : "Not a CSV statement"}</span
          >
          {#if f.header.length || guess}
            <button
              type="button"
              class="qb-secondary small"
              onclick={() => (wizard = { editing: null, file: f.filename })}
            >
              Set up account for this file
            </button>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<details class="advanced">
  <summary>Advanced: supported banks and settings file</summary>
  {#if setup.config_file}
    <p class="muted">
      Settings are saved in <code>favabooks-import.json</code> next to
      <code>{setup.config_file}</code>. Files are read from {#each setup.import_dirs as dir (dir)}<code
          >{dir}</code
        >
      {/each}.
    </p>
  {/if}
  <table>
    <thead
      ><tr
        ><th>Bank</th><th>Account types</th><th>Download in online banking</th
        ></tr
      ></thead
    >
    <tbody>
      {#each setup.banks as b (b.bank)}
        <tr>
          <td><strong>{b.bank}</strong></td>
          <td
            >{#each b.formats as f (f.key)}<span class="chip"
                >{f.kind}{f.confidence === "unverified"
                  ? " (unverified)"
                  : ""}</span
              >
            {/each}</td
          >
          <td class="muted">{b.formats[0]?.download ?? ""}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</details>

{#if wizard}
  <AddAccount
    {setup}
    editing={wizard.editing}
    file={wizard.file}
    onclose={() => (wizard = null)}
    onsaved={saved}
  />
{/if}

<style>
  .page-head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .page-head p {
    max-width: 46rem;
    margin: 0;
  }

  .muted {
    color: var(--qb-muted);
  }

  .add,
  .empty .qb-primary {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
  }

  .error {
    color: var(--error);
  }

  .off,
  .empty {
    display: flex;
    gap: 1.2rem;
    align-items: flex-start;
    margin-bottom: 1rem;
  }

  .empty {
    flex-direction: column;
    align-items: center;
    padding: 2.5rem 1rem;
    text-align: center;
  }

  .off h2,
  .empty h2 {
    margin: 0 0 0.4rem;
    font-size: 1.15rem;
  }

  .big-icon {
    display: grid;
    flex: none;
    place-items: center;
    width: 52px;
    height: 52px;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .account {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .top {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  .avatar {
    display: grid;
    flex: none;
    place-items: center;
    width: 40px;
    height: 40px;
    font-weight: 700;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  .title {
    display: flex;
    flex-direction: column;
  }

  .posts,
  .meta {
    margin: 0;
    font-size: 0.9rem;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .chip {
    padding: 0.1rem 0.6rem;
    font-size: 0.78rem;
    color: var(--text-color-lighter);
    background: var(--background-darker);
    border-radius: 999px;
  }

  .help {
    display: flex;
    gap: 0.4rem;
    align-items: flex-start;
    padding: 0.5rem 0.7rem;
    margin: 0;
    font-size: 0.9rem;
    background: var(--qb-accent-soft);
    border-radius: 8px;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1rem;
    align-items: center;
    padding-top: 0.6rem;
    margin-top: auto;
    border-top: 1px solid var(--border-lighter);
  }

  .small {
    padding: 0.3em 1em;
    font-size: 0.88em;
  }

  a.button {
    color: var(--button-color);
    background: var(--button-background);
  }

  .link {
    padding: 0;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }

  .link.danger {
    color: var(--error);
  }

  .waiting {
    margin-bottom: 1rem;
  }

  .waiting h3 {
    margin: 0 0 0.6rem;
    font-size: 1rem;
  }

  .waiting ul {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .waiting li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.8rem;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-lighter);
  }

  .file {
    font-weight: 600;
  }

  .waiting li button {
    margin-left: auto;
  }

  .advanced {
    margin-top: 1.5rem;
  }

  .advanced summary {
    font-weight: 600;
    color: var(--qb-muted);
    cursor: pointer;
  }

  .advanced table {
    --table-background-even: transparent;

    width: 100%;
    margin-top: 0.6rem;
  }

  .advanced td {
    white-space: normal;
  }
</style>
