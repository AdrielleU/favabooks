<script lang="ts">
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import { url_for } from "../../helpers.ts";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { accounts_set } from "../../stores/index.ts";
  import type { QbEditResult, QbReview, QbReviewRow } from "../api.ts";
  import { put_qb_accept } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";

  let { review }: { review: QbReview } = $props();

  /** Category picked per row (entry hash -> account). */
  let chosen = $state<Record<string, string>>({});
  /** Selected rows (entry hash -> true). */
  let selected = $state<Record<string, boolean>>({});
  /** Account card the table is filtered to ("" for all). */
  let only = $state("");
  let bulk_category = $state("");
  let busy = $state(false);

  $effect.pre(() => {
    chosen = Object.fromEntries(
      review.rows.map((row) => [row.entry_hash, row.categories[0] ?? ""]),
    );
    selected = {};
    if (!review.accounts.some((a) => a.account === only)) {
      only = "";
    }
  });

  const is_split = (row: QbReviewRow) => row.categories.length !== 1;
  const leaf = (account: string) => account.split(":").slice(1).join(":");

  let rows = $derived(
    only ? review.rows.filter((row) => row.account === only) : review.rows,
  );
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

<div class="page-actions">
  <span class="muted">
    Imported transactions waiting to be categorised and accepted.
  </span>
  <a class="button qb-secondary" href={$url_for("import/")}>
    <Icon name="upload" size={16} /> Upload file
  </a>
</div>

{#if review.accounts.length}
  <div class="accounts">
    <button
      type="button"
      class="account-card"
      class:active={only === ""}
      onclick={() => (only = "")}
    >
      <span class="card-label"
        ><Icon name="inbox" size={16} /> All accounts</span
      >
      <strong>{review.rows.length}</strong>
      <span class="muted">to review</span>
    </button>
    {#each review.accounts as acct (acct.account)}
      <button
        type="button"
        class="account-card"
        class:active={only === acct.account}
        onclick={() => (only = only === acct.account ? "" : acct.account)}
        title={acct.account}
      >
        <span class="card-label">
          <Icon
            name={acct.account.startsWith("Liabilities")
              ? "wallet"
              : "landmark"}
            size={16}
          />
          {leaf(acct.account)}
        </span>
        <strong>{acct.to_review}</strong>
        <span class="muted">
          to review · in books {money(acct.balance, acct.currency)}
        </span>
      </button>
    {/each}
  </div>
{/if}

{#if review.rows.length === 0}
  <div class="qb-card empty">
    <span class="empty-icon"><Icon name="circle-check" size={28} /></span>
    <h2>You're all caught up</h2>
    <p class="muted">
      Imported transactions flagged <code>!</code> show up here. Clear the header
      filters if you expected some.
    </p>
  </div>
{:else}
  <div class="qb-card table-card">
    <div class="toolbar" class:batch={selected_rows.length > 0}>
      {#if selected_rows.length}
        <strong>{selected_rows.length} selected</strong>
        <button
          type="button"
          class="qb-primary"
          disabled={busy}
          onclick={async () => accept(selected_rows)}
        >
          Accept selected
        </button>
        <span class="muted">or categorize as</span>
        <span class="picker"><AccountInput bind:value={bulk_category} /></span>
        <button
          type="button"
          class="qb-secondary"
          disabled={busy || !bulk_category}
          onclick={async () => accept(selected_rows, bulk_category)}
        >
          Categorize &amp; accept
        </button>
      {:else}
        <span class="tab"
          >For review <span class="count">{rows.length}</span></span
        >
        <span class="muted">
          {only ? leaf(only) : "All accounts"} · within the header filters
        </span>
      {/if}
    </div>
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
          <th class="action-col">Action</th>
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
            <td class="date">{short_date(row.date)}</td>
            <td>
              <a href={`#context-${row.entry_hash}`} title="Show transaction">
                <strong>{row.payee || row.narration}</strong>
                {#if row.payee && row.narration}
                  <span class="narration">{row.narration}</span>
                {/if}
              </a>
            </td>
            <td class="muted" title={row.account}>{leaf(row.account)}</td>
            <td class="num">
              {row.amount < 0 ? money(-row.amount, row.currency) : ""}
            </td>
            <td class="num received">
              {row.amount > 0 ? money(row.amount, row.currency) : ""}
            </td>
            <td class="category">
              {#if is_split(row)}
                <span class="chip" title={row.categories.join("\n")}>
                  Split · {row.categories.length}
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
            <td class="action-col">
              <button
                type="button"
                class="qb-primary small"
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
  .page-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .muted,
  .narration {
    font-weight: normal;
    color: var(--qb-muted);
  }

  a.button {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
  }

  .accounts {
    display: flex;
    gap: 0.75rem;
    padding-bottom: 0.25rem;
    margin-bottom: 1rem;
    overflow-x: auto;
  }

  .account-card {
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 12.5rem;
    padding: 0.85rem 1rem;
    font-weight: normal;
    color: var(--text-color);
    text-align: left;
    background: var(--qb-surface);
    border: 1px solid var(--border-lighter);
    border-top: 3px solid transparent;
    border-radius: var(--qb-radius);
    box-shadow: var(--qb-shadow);
  }

  .account-card.active {
    border-top-color: var(--qb-accent);
  }

  .card-label {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    font-weight: 600;
  }

  .account-card strong {
    font-size: 1.5rem;
    font-weight: 650;
  }

  .account-card .muted {
    font-size: 0.82rem;
  }

  .table-card {
    padding: 0;
    overflow-x: auto;
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.9rem;
    align-items: center;
    min-height: 3.25rem;
    padding: 0.5rem 1rem;
    border-bottom: 1px solid var(--border);
  }

  .toolbar.batch {
    background: var(--qb-accent-soft);
  }

  .tab {
    padding-bottom: 0.2rem;
    font-weight: 600;
    border-bottom: 2px solid var(--qb-accent);
  }

  .count {
    padding: 0 0.45rem;
    margin-left: 0.2rem;
    font-size: 0.8em;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 999px;
  }

  .picker {
    min-width: 15rem;
  }

  table {
    width: 100%;
    margin: 0;
    border: none;
  }

  th {
    text-align: left;
    white-space: nowrap;
  }

  td {
    vertical-align: middle;
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
    text-align: right;
  }

  .received {
    color: var(--diff-positive);
  }

  td a {
    color: inherit;
  }

  .table-card td a strong {
    font-weight: 600;
  }

  .narration {
    display: block;
    font-size: 0.88em;
  }

  .category {
    min-width: 15rem;
  }

  /* Category boxes read as text until hovered or focused. */
  .category :global(input) {
    background: transparent;
    border-color: transparent;
  }

  tr:hover .category :global(input),
  .category :global(input:focus) {
    background: var(--qb-surface);
    border-color: var(--border-darker);
  }

  .chip {
    display: inline-block;
    padding: 0.1rem 0.6rem;
    font-size: 0.85em;
    color: var(--text-color-lighter);
    background: var(--background-darker);
    border-radius: 999px;
  }

  .action-col {
    width: 1px;
    text-align: right;
  }

  .small {
    padding: 0.3em 1em;
    font-size: 0.9em;
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 3rem 1rem;
    text-align: center;
  }

  .empty-icon {
    color: var(--qb-accent);
  }

  .empty h2 {
    margin: 0.5rem 0 0.25rem;
  }

  .empty p {
    margin: 0;
  }
</style>
