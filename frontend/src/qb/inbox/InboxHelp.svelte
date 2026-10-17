<!--
  qb-fork: "Add your files" popup. Opens by itself while the books have no
  documents yet (until closed for this session, or "Don't show again"), and
  from "+ New → Add files to the inbox". Says where the inbox folder is and
  how to copy or move files into it on Windows, Mac and Linux, then how to
  import them: on the Import page or with an AI assistant.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import ModalBase from "../../modals/ModalBase.svelte";
  import { base_url } from "../../stores/index.ts";
  import type { QbInbox } from "../api.ts";
  import { get_qb_inbox } from "../api.ts";
  import Icon from "../Icon.svelte";
  import type { Os } from "./help.ts";
  import {
    copy_command,
    detect_os,
    inbox_help_open,
    OS_NAMES,
    parent_folder,
    steps,
  } from "./help.ts";

  const HIDE_KEY = "favabooks-inbox-help-hidden";
  const OSES: Os[] = ["windows", "mac", "linux"];

  let info = $state<QbInbox | null>(null);
  let os = $state<Os>(detect_os(navigator.userAgent));
  let copied = $state(false);

  function hidden(key: string, storage: () => Storage): boolean {
    try {
      return storage().getItem(`${HIDE_KEY}:${key}`) === "1";
    } catch {
      return false;
    }
  }

  function hide(key: string, storage: () => Storage) {
    try {
      storage().setItem(`${HIDE_KEY}:${key}`, "1");
    } catch {
      // Storage can be unavailable (private windows); it shows again.
    }
  }

  $effect(() => {
    const books = $base_url;
    get_qb_inbox().then(
      (data) => {
        info = data;
        if (
          data.documents === 0 &&
          !hidden(books, () => sessionStorage) &&
          !hidden(books, () => localStorage)
        ) {
          inbox_help_open.set(true);
        }
      },
      () => {
        info = null;
      },
    );
  });

  // Reload when opened from the menu, so the file list is current.
  $effect(() => {
    if ($inbox_help_open) {
      get_qb_inbox().then(
        (data) => {
          info = data;
        },
        () => {
          // Keep showing what was loaded before.
        },
      );
    }
  });

  function close() {
    hide($base_url, () => sessionStorage);
    inbox_help_open.set(false);
    copied = false;
  }

  function never() {
    hide($base_url, () => localStorage);
    close();
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch {
      copied = false;
    }
  }

  let path = $derived(info?.inbox ?? null);
  let relative = $derived(info?.relative ?? "books/inbox");
  let books_folder = $derived(
    path !== null ? parent_folder(path) : parent_folder(relative),
  );
</script>

<ModalBase shown={$inbox_help_open && info !== null} close_handler={close}>
  {#if info}
    <div class="help">
      <h2><Icon name="inbox" /> Add your files</h2>
      <p>
        Copy or move your <strong>bank and card statements</strong> (CSV
        downloads), <strong>receipts</strong> and <strong>invoices</strong>
        (PDFs or photos) into your books' <strong>inbox</strong> folder:
      </p>

      {#if path !== null}
        <div class="path">
          <code class="path-text">{path}</code>
          <button
            type="button"
            class="qb-secondary small"
            onclick={async () => copy(path)}
          >
            {copied ? "Copied" : "Copy path"}
          </button>
        </div>
      {:else if info.relative !== null}
        <div class="path">
          <code class="path-text">{relative}</code>
          <span class="muted">in the folder with docker-compose.yml</span>
        </div>
      {:else}
        <p class="muted">
          These books have no inbox folder yet. Add one in Advanced → Edit
          ledger files: <code
            >2020-01-01 custom "fava-option" "import-dirs" "inbox"</code
          >
        </p>
      {/if}

      <div class="tabs" role="tablist">
        {#each OSES as name (name)}
          <button
            type="button"
            role="tab"
            aria-selected={os === name}
            class:active={os === name}
            onclick={() => (os = name)}
          >
            {OS_NAMES[name]}
          </button>
        {/each}
      </div>
      <ol>
        {#each steps(os, path, relative) as step (step)}
          <li>{step}</li>
        {/each}
        {#if path !== null}
          <li>
            Or in a terminal{os === "windows" ? " (PowerShell)" : ""}:
            <code>{copy_command(os, path)}</code>
          </li>
        {/if}
      </ol>

      {#if info.file_count > 0}
        <div class="waiting">
          <strong>
            {info.file_count}
            {info.file_count === 1 ? "file is" : "files are"} waiting in the inbox:
          </strong>
          {info.files.join(", ")}{info.file_count > info.files.length
            ? ", …"
            : ""}
        </div>
      {/if}

      <h3>Then import them</h3>
      <div class="ways">
        <div class="way">
          <strong>In Favabooks</strong>
          <p class="muted">
            Banking → Import files reads the bank and card CSVs of accounts you
            connected in Bank &amp; card accounts. Then accept the new entries
            in For review.
          </p>
          <a
            class="button qb-primary small go"
            href={$url_for("import/")}
            onclick={close}
          >
            Import files
          </a>
        </div>
        <div class="way">
          <strong>With an AI assistant</strong>
          <p class="muted">
            Run Claude Code, Codex or another coding assistant in your books
            folder (<code>{books_folder}</code>) and ask it to "import the
            inbox" (in Claude Code:
            <code class="nowrap">/import-inbox</code>). It follows the books'
            AGENTS.md and adds entries for you to accept in For review.
          </p>
        </div>
      </div>

      <div class="foot">
        <button type="button" class="link muted" onclick={never}>
          Don't show this again
        </button>
        <button type="button" class="qb-secondary" onclick={close}>Done</button>
      </div>
    </div>
  {/if}
</ModalBase>

<style>
  .help {
    padding-right: 1.5em;
  }

  h2 {
    display: flex;
    gap: 0.5em;
    align-items: center;
    margin: 0 0 0.6em;
  }

  h3 {
    margin: 1.2em 0 0.5em;
    font-size: 1.05em;
  }

  .muted {
    color: var(--qb-muted);
  }

  .path {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6em;
    align-items: center;
    padding: 0.6em 0.8em;
    margin: 0.6em 0;
    background: var(--background-darker);
    border-radius: 8px;
  }

  .path-text {
    flex: 1 1 16em;
    overflow-wrap: anywhere;
  }

  .tabs {
    display: flex;
    gap: 0.3em;
    margin-top: 1em;
    border-bottom: 1px solid var(--border);
  }

  .tabs button {
    padding: 0.4em 1em;
    color: var(--qb-muted);
    background: none;
    border: 0;
    border-bottom: 2px solid transparent;
    border-radius: 0;
  }

  .tabs button.active {
    color: var(--text-color);
    border-bottom-color: var(--qb-accent);
  }

  ol {
    padding-left: 1.4em;
    margin: 0.8em 0;
  }

  li {
    margin-bottom: 0.4em;
  }

  li code,
  .way code {
    overflow-wrap: anywhere;
  }

  .nowrap {
    white-space: nowrap;
  }

  .waiting {
    padding: 0.6em 0.8em;
    background: var(--qb-accent-soft);
    border-radius: 8px;
  }

  .ways {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15em, 1fr));
    gap: 0.8em;
  }

  .way {
    padding: 0.8em;
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  .way p {
    margin: 0.4em 0 0.6em;
  }

  .small {
    padding: 0.3em 1em;
    font-size: 0.88em;
  }

  .go,
  .go:hover {
    color: var(--button-color);
  }

  .foot {
    display: flex;
    gap: 1em;
    align-items: center;
    justify-content: flex-end;
    margin-top: 1.2em;
  }

  .link {
    padding: 0;
    text-decoration: underline;
    background: none;
    border: 0;
  }
</style>
