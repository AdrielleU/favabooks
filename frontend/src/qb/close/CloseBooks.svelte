<!--
  qb-fork: Close books. Lock everything on or before a date: Favabooks
  refuses changes there, and balance checks flag changes made elsewhere.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import type { QbCheck, QbCloseState } from "../api.ts";
  import { delete_qb_close, put_qb_close } from "../api.ts";
  import { iso } from "../docs/periods.ts";
  import { short_date } from "../format.ts";
  import Icon from "../Icon.svelte";

  let {
    info,
    checks,
    year,
  }: { info: QbCloseState; checks: QbCheck[]; year: number } = $props();

  let date = $derived(iso(info.suggested));
  let note = $state("");
  let busy = $state(false);
  let confirm_reopen = $state(false);
  let open_items = $derived(checks.filter((c) => !c.ok));
  let latest = $derived(info.history[0]);

  const check_url = (c: QbCheck) => $url_for(`${c.report}/`, c.params);

  function pick_date(value: string) {
    date = value;
    const url = new URL(window.location.href);
    url.searchParams.set("date", value);
    router.navigate(url);
  }

  async function close(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    try {
      notify(await put_qb_close({ date, note }));
      note = "";
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }

  async function reopen() {
    busy = true;
    try {
      notify(await delete_qb_close());
      confirm_reopen = false;
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }
</script>

<div class="qb-card status" class:closed={info.closed_through !== null}>
  <span class="big-icon"><Icon name="lock" size={26} /></span>
  <div class="status-text">
    {#if info.closed_through && latest}
      <h2>Books are closed through {short_date(info.closed_through)}</h2>
      <p class="muted">
        Closed with {latest.checks} balance checks{latest.note
          ? ` · ${latest.note}`
          : ""}. Nothing dated on or before it can change in Favabooks; a change
        made any other way shows up as an error.
      </p>
    {:else}
      <h2>Books are open</h2>
      <p class="muted">
        Close a period once it's final (usually after your accountant files the
        year), so nothing in it changes by accident.
      </p>
    {/if}
  </div>
  {#if info.closed_through}
    {#if confirm_reopen}
      <div class="confirm">
        <span
          >{info.history[1]
            ? `Reopen everything after ${short_date(info.history[1].date)}?`
            : "Reopen the books? Everything becomes editable again."}</span
        >
        <button
          type="button"
          class="qb-secondary"
          onclick={() => (confirm_reopen = false)}>Cancel</button
        >
        <button
          type="button"
          class="qb-primary danger"
          disabled={busy}
          onclick={reopen}>Reopen</button
        >
      </div>
    {:else}
      <button
        type="button"
        class="qb-secondary"
        onclick={() => (confirm_reopen = true)}
      >
        Reopen
      </button>
    {/if}
  {/if}
</div>

<div class="grid">
  <form class="qb-card" onsubmit={close}>
    <h3>Close the books</h3>
    <label>
      <span class="cap">Closing date</span>
      <input
        type="date"
        value={date}
        max={iso(new Date(info.today.getTime() - 86_400_000))}
        onchange={(e) => {
          pick_date(e.currentTarget.value);
        }}
        required
      />
    </label>
    <label>
      <span class="cap">Note (optional)</span>
      <input bind:value={note} placeholder="e.g. 2025 taxes filed by CPA" />
    </label>
    <p class="muted small">
      Favabooks adds a "closed-books" entry and a balance check for every
      account as of that date. You can reopen later; the checks are removed with
      it.
    </p>
    <button type="submit" class="qb-primary" disabled={busy || !date}>
      <Icon name="lock" size={15} /> Close books through {date}
    </button>
  </form>

  <div class="qb-card">
    <h3>
      Before you close {year}
      <span class="pill" class:done={open_items.length === 0}
        >{checks.length - open_items.length} of {checks.length} ready</span
      >
    </h3>
    <ul class="checks">
      {#each checks as c (c.key)}
        <li class:ok={c.ok}>
          <Icon name={c.ok ? "circle-check" : "triangle-alert"} size={16} />
          <div>
            <strong>{c.title}</strong>
            <span class="muted sub">{c.detail}</span>
          </div>
          {#if !c.ok}<a href={check_url(c)}>Fix</a>{/if}
        </li>
      {/each}
    </ul>
    <p class="muted small">
      These are suggestions; you can close with items left. It's usually better
      to sort them out first.
    </p>
  </div>
</div>

{#if info.history.length}
  <h3 class="history-title">History</h3>
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr
          ><th>Closed through</th><th>Note</th><th class="num"
            >Balance checks</th
          ></tr
        >
      </thead>
      <tbody>
        {#each info.history as h (h.entry_hash)}
          <tr>
            <td>{short_date(h.date)}</td>
            <td>{h.note}</td>
            <td class="num">{h.checks}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .muted {
    color: var(--qb-muted);
  }

  .small {
    font-size: 0.88em;
  }

  .sub {
    display: block;
    font-size: 0.9em;
  }

  .status {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
    margin-bottom: 1rem;
  }

  .status-text {
    flex: 1;
    min-width: min(100%, 20rem);
  }

  .status h2 {
    margin: 0 0 0.3rem;
    font-size: 1.15rem;
  }

  .status p {
    margin: 0;
  }

  .big-icon {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    color: var(--qb-muted);
    background: var(--background-darker);
    border-radius: 50%;
  }

  .closed .big-icon {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }

  .confirm {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  .danger {
    background: var(--error);
    border-color: var(--error);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }

  form {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }

  h3 {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin: 0 0 0.6rem;
    font-size: 1rem;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .cap {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  form button {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
    align-self: flex-start;
  }

  .pill {
    padding: 0.1em 0.6em;
    font-size: 0.8em;
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 12%, transparent);
    border-radius: 999px;
  }

  .pill.done {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }

  .checks {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .checks li {
    display: flex;
    gap: 0.6rem;
    align-items: flex-start;
    padding: 0.5rem 0;
    color: var(--warning);
    border-bottom: 1px solid var(--border-lighter);
  }

  .checks li.ok {
    color: var(--qb-accent);
  }

  .checks li div {
    flex: 1;
    color: var(--text-color);
  }

  .checks a {
    font-weight: 600;
    color: var(--qb-accent);
  }

  .history-title {
    margin-top: 0.5rem;
  }

  .table-card {
    padding: 0;
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
    text-align: left;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-weight: 500;
    color: var(--text-color-lighter);
    background: var(--background-darker);
  }

  .num {
    text-align: right;
  }
</style>
