<script lang="ts">
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import { day } from "../../format.ts";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { ctx } from "../../stores/format.ts";
  import { accounts_set } from "../../stores/index.ts";
  import type { QbEditResult, QbReviewRow } from "../api.ts";
  import { put_qb_accept } from "../api.ts";

  let { rows }: { rows: QbReviewRow[] } = $props();

  /** Category picked per row (entry hash -> account). */
  let chosen = $state<Record<string, string>>({});
  /** Selected rows (entry hash -> true). */
  let selected = $state<Record<string, boolean>>({});
  let bulk_category = $state("");
  let busy = $state(false);

  $effect.pre(() => {
    chosen = Object.fromEntries(
      rows.map((row) => [row.entry_hash, row.categories[0] ?? ""]),
    );
    selected = {};
  });

  const is_split = (row: QbReviewRow) => row.categories.length !== 1;
  const leaf = (account: string) => account.split(":").slice(1).join(":");

  let selected_rows = $derived(
    rows.filter((row) => selected[row.entry_hash] === true),
  );
  let all_selected = $derived(
    rows.length > 0 && selected_rows.length === rows.length,
  );

  function toggle_all() {
    const value = !all_selected;
    selected = Object.fromEntries(rows.map((row) => [row.entry_hash, value]));
  }

  /**
   * Accept rows, changing each one's category to `to_override` or to the one
   * picked in its row. Rows sharing the same change go in one request.
   */
  async function accept(targets: QbReviewRow[], to_override?: string) {
    // A plain object: this is local to one call, not reactive state.
    const groups: Record<
      string,
      { from: string; to: string; hashes: string[] }
    > = {};
    let unchanged_splits = 0;
    for (const row of targets) {
      const from = row.categories[0] ?? "";
      let to = to_override ?? chosen[row.entry_hash] ?? from;
      if (is_split(row)) {
        unchanged_splits += to_override === undefined ? 0 : 1;
        to = from;
      }
      if (to !== from && !$accounts_set.has(to)) {
        notify(`"${to}" is not an open account.`, "error");
        return;
      }
      const change = to === from ? { from: "", to: "" } : { from, to };
      const key = `${change.from}\u0000${change.to}`;
      const group = groups[key] ?? { ...change, hashes: [] };
      group.hashes.push(row.entry_hash);
      groups[key] = group;
    }

    busy = true;
    const results: QbEditResult[] = [];
    try {
      for (const { from, to, hashes } of Object.values(groups)) {
        results.push(
          await put_qb_accept(
            to
              ? { entry_hashes: hashes, from_account: from, to_account: to }
              : { entry_hashes: hashes },
          ),
        );
      }
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }

    const changed = results.reduce((n, r) => n + r.changed, 0);
    const failed = results.flatMap((r) => r.failed);
    if (changed) {
      notify(
        `Accepted ${changed.toString()} transaction${changed === 1 ? "" : "s"}.`,
      );
    }
    if (unchanged_splits) {
      notify(
        `${unchanged_splits.toString()} split transaction(s) accepted without a category change.`,
        "warning",
      );
    }
    if (failed[0]) {
      notify(
        `${failed.length.toString()} could not be saved: ${failed[0].error}`,
        "error",
      );
    }
    router.reload();
  }
</script>

{#if rows.length === 0}
  <div class="qb-card empty">
    <h2>Nothing to review</h2>
    <p>
      Imported transactions flagged <code>!</code> show up here. Clear the header
      filters if you expected some.
    </p>
  </div>
{:else}
  <div class="toolbar">
    {#if selected_rows.length}
      <span>{selected_rows.length} selected</span>
      <button
        type="button"
        disabled={busy}
        onclick={async () => accept(selected_rows)}
      >
        Accept selected
      </button>
      <span class="sep">or categorize as</span>
      <span class="picker"><AccountInput bind:value={bulk_category} /></span>
      <button
        type="button"
        disabled={busy || !bulk_category}
        onclick={async () => accept(selected_rows, bulk_category)}
      >
        Categorize &amp; accept
      </button>
    {:else}
      <span class="hint">
        {rows.length} transaction{rows.length === 1 ? "" : "s"} to review, within
        the header filters. Select rows to accept or categorize several at once.
      </span>
    {/if}
  </div>

  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th class="check">
            <input
              type="checkbox"
              aria-label="Select all"
              checked={all_selected}
              onchange={toggle_all}
            />
          </th>
          <th>Date</th>
          <th>Description</th>
          <th>Account</th>
          <th class="num">Spent</th>
          <th class="num">Received</th>
          <th>Category</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row (row.entry_hash)}
          <tr class:selected={selected[row.entry_hash]}>
            <td class="check">
              <input
                type="checkbox"
                aria-label="Select"
                bind:checked={selected[row.entry_hash]}
              />
            </td>
            <td class="date">{day(row.date)}</td>
            <td>
              <a href={`#context-${row.entry_hash}`} title="Show transaction">
                <strong>{row.payee || row.narration}</strong>
                {#if row.payee && row.narration}
                  <span class="narration">{row.narration}</span>
                {/if}
              </a>
            </td>
            <td title={row.account}>{leaf(row.account)}</td>
            <td class="num">
              {row.amount < 0 ? $ctx.amount(-row.amount, row.currency) : ""}
            </td>
            <td class="num">
              {row.amount > 0 ? $ctx.amount(row.amount, row.currency) : ""}
            </td>
            <td class="category">
              {#if is_split(row)}
                <span class="split" title={row.categories.join("\n")}>
                  Split ({row.categories.length})
                </span>
              {:else}
                <AccountInput
                  bind:value={
                    () => chosen[row.entry_hash] ?? "",
                    (value: string) => {
                      chosen[row.entry_hash] = value;
                    }
                  }
                />
              {/if}
            </td>
            <td>
              <button
                type="button"
                disabled={busy}
                onclick={async () => accept([row])}
              >
                Accept
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.75rem;
    align-items: center;
    min-height: 2.4rem;
    margin-bottom: 0.75rem;
  }

  .hint,
  .sep,
  .narration {
    color: var(--text-color-lightest);
  }

  .picker {
    min-width: 16rem;
  }

  .table-card {
    padding: 0;
    overflow-x: auto;
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0;
    border: none;
  }

  th,
  td {
    padding: 0.5em 0.75em;
    vertical-align: middle;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-weight: 500;
    color: var(--text-color-lighter);
    text-align: left;
    background: var(--background-darker);
  }

  tr.selected td {
    background: color-mix(in srgb, var(--qb-accent) 8%, transparent);
  }

  .check {
    width: 1px;
  }

  .date,
  .num {
    white-space: nowrap;
  }

  .num {
    font-family: var(--font-family-monospaced);
    text-align: right;
  }

  td a {
    color: inherit;
  }

  td a strong {
    font-weight: 500;
  }

  .narration {
    display: block;
    font-size: 0.9em;
  }

  .category {
    min-width: 14rem;
  }

  .split {
    color: var(--text-color-lightest);
  }

  .empty h2 {
    margin-top: 0;
  }

  .empty p {
    margin-bottom: 0;
  }
</style>
