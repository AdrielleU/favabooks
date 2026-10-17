<!--
  qb-fork: Business details & dates. Beancount events, shown as the
  current value of each detail (address, tax status, ...) with its history,
  plus future-dated reminders.
-->
<script lang="ts">
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import type { QbEvents } from "../api.ts";
  import { delete_qb_event, put_qb_event } from "../api.ts";
  import { short_date } from "../format.ts";
  import Icon from "../Icon.svelte";

  let { data }: { data: QbEvents } = $props();

  const today = new Date().toISOString().slice(0, 10);
  let form = $state({ date: today, type: "", description: "" });
  let busy = $state(false);

  const ACRONYMS = new Set(["ein", "ssn", "llc", "irs", "tin", "dba"]);
  const label = (type: string) =>
    type
      .split("-")
      .map((w, i) =>
        ACRONYMS.has(w)
          ? w.toUpperCase()
          : i === 0
            ? w.replace(/^./, (c) => c.toUpperCase())
            : w,
      )
      .join(" ");
  let upcoming = $derived(
    data.events
      .filter((e) => e.date > data.today)
      .toSorted((a, b) => a.date.getTime() - b.date.getTime()),
  );
  const days_until = (d: Date) =>
    Math.round((d.getTime() - data.today.getTime()) / 86_400_000);

  function start(type: string) {
    form = { date: today, type, description: "" };
    document.getElementById("event-description")?.focus();
  }

  async function add(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    try {
      notify(await put_qb_event(form));
      form = { date: today, type: "", description: "" };
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }

  async function remove(entry_hash: string) {
    try {
      notify(await delete_qb_event(entry_hash));
      router.reload();
    } catch (error) {
      notify_err(error);
    }
  }
</script>

<p class="intro muted">
  Facts about the business that change now and then: address, registered agent,
  tax status, licenses. Each holds from its date until the next one of the same
  kind. Date one in the future to make it a reminder.
</p>

{#if upcoming.length}
  <div class="qb-card reminders">
    <h3><Icon name="bell" size={16} /> Coming up</h3>
    <ul>
      {#each upcoming as e (e.entry_hash)}
        <li>
          <strong>{short_date(e.date)}</strong>
          <span class="muted">in {days_until(e.date)} days</span>
          <span>{label(e.type)}: {e.description}</span>
        </li>
      {/each}
    </ul>
  </div>
{/if}

{#if data.types.length}
  <div class="cards">
    {#each data.types as t (t.type)}
      <div class="qb-card detail">
        <span class="kind">{label(t.type)}</span>
        {#if t.current}
          <strong>{t.current.description}</strong>
          <span class="muted">since {short_date(t.current.date)}</span>
        {:else}
          <span class="muted">Nothing current yet</span>
        {/if}
        {#if t.upcoming}
          <span class="next"
            >Next: {t.upcoming.description} on {short_date(
              t.upcoming.date,
            )}</span
          >
        {/if}
        <button
          type="button"
          class="link"
          onclick={() => {
            start(t.type);
          }}>Update</button
        >
      </div>
    {/each}
  </div>
{/if}

<form class="qb-card add" onsubmit={add}>
  <h3>
    {data.types.length ? "Add or update a detail" : "Add your first detail"}
  </h3>
  <div class="fields">
    <label>
      <span class="cap">Kind</span>
      <input
        list="qb-event-types"
        bind:value={form.type}
        placeholder="address"
        required
      />
      <datalist id="qb-event-types">
        {#each [...data.types.map((t) => t.type), ...data.suggestions] as s (s)}
          <option value={s}></option>
        {/each}
      </datalist>
    </label>
    <label class="wide">
      <span class="cap">Value</span>
      <input
        id="event-description"
        bind:value={form.description}
        placeholder="e.g. 1 Main St, Phoenix, AZ 85001"
        required
      />
    </label>
    <label>
      <span class="cap">From</span>
      <input type="date" bind:value={form.date} required />
    </label>
  </div>
  {#if data.suggestions.length}
    <p class="muted small">
      Ideas:
      {#each data.suggestions.slice(0, 6) as s (s)}
        <button
          type="button"
          class="chip"
          onclick={() => {
            start(s);
          }}>{label(s)}</button
        >
      {/each}
    </p>
  {/if}
  <button type="submit" class="qb-primary" disabled={busy}>Save</button>
</form>

{#if data.events.length}
  <h3 class="history-title">History</h3>
  <div class="qb-card table-card">
    <table>
      <tbody>
        {#each data.events as e (e.entry_hash)}
          <tr class:future={e.date > data.today}>
            <td class="nowrap">
              {short_date(e.date)}
              {#if e.date > data.today}<span class="upcoming">Upcoming</span
                >{/if}
            </td>
            <td class="nowrap">{label(e.type)}</td>
            <td>{e.description}</td>
            <td class="actions">
              <button
                type="button"
                class="link danger"
                onclick={async () => remove(e.entry_hash)}>Delete</button
              >
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .intro {
    max-width: 52rem;
    margin: 0 0 1rem;
  }

  .muted {
    color: var(--qb-muted);
  }

  .small {
    font-size: 0.88em;
  }

  h3 {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    margin: 0 0 0.6rem;
    font-size: 1rem;
  }

  .reminders {
    margin-bottom: 1rem;
    border-left: 4px solid var(--warning);
  }

  .reminders ul {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .reminders li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 0.8rem;
    padding: 0.3rem 0;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 16rem), 1fr));
    gap: 0.8rem;
    margin-bottom: 1rem;
  }

  .detail {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .kind {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--qb-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .next {
    font-size: 0.85em;
    font-weight: 600;
  }

  .link {
    align-self: flex-start;
    padding: 0;
    margin-top: 0.3rem;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }

  .link.danger {
    margin: 0;
    color: var(--error);
  }

  .add {
    margin-bottom: 1rem;
  }

  .fields {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 2fr) minmax(0, 1fr);
    gap: 0.6rem;
    margin-bottom: 0.7rem;
  }

  @media (width <= 700px) {
    .fields {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .cap {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .chip {
    padding: 0.1em 0.7em;
    margin: 0 0.2rem 0.2rem 0;
    font-size: 0.9em;
    color: var(--text-color);
    background: var(--background-darker);
    border-radius: 999px;
  }

  .history-title {
    margin-top: 0.5rem;
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

  td {
    padding: 0.5em 0.75em;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  tr.future td {
    background: color-mix(in srgb, var(--warning) 8%, transparent);
  }

  .upcoming {
    display: inline-block;
    padding: 0 0.5em;
    margin-left: 0.4em;
    font-size: 0.75em;
    font-weight: 600;
    border: 1px solid currentcolor;
    border-radius: 999px;
  }

  .nowrap {
    white-space: nowrap;
  }

  .actions {
    text-align: right;
  }
</style>
