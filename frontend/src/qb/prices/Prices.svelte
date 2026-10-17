<!--
  qb-fork: Currencies & prices. The currencies the books use besides the
  home one, their prices (to convert them in reports), and which ones
  still need one.
-->
<script lang="ts">
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import type { QbPrices } from "../api.ts";
  import { delete_qb_price, put_qb_price } from "../api.ts";
  import { change_text } from "../charts/data.ts";
  import TrendChart from "../charts/TrendChart.svelte";
  import { short_date } from "../format.ts";
  import Icon from "../Icon.svelte";

  let { data }: { data: QbPrices } = $props();

  const today = new Date().toISOString().slice(0, 10);
  let form = $state({ date: today, currency: "", price: "", quote: "" });
  let selected = $state("");
  let busy = $state(false);

  let needing = $derived(data.currencies.filter((c) => c.needs_price));
  let used = $derived(data.currencies.filter((c) => c.postings > 0));
  let shown = $derived(selected || (data.currencies[0]?.currency ?? ""));
  let history = $derived(
    data.prices
      .filter((p) => p.currency === shown)
      .toSorted((a, b) => a.date.getTime() - b.date.getTime()),
  );
  let quote = $derived(history[history.length - 1]?.quote ?? data.home);
  const fmt = (n: number) =>
    n.toLocaleString(undefined, { maximumFractionDigits: 6 });

  function prefill(currency: string) {
    form = { date: today, currency, price: "", quote: data.home };
    selected = currency;
    document
      .getElementById("price-form")
      ?.scrollIntoView({ behavior: "smooth" });
  }

  async function add(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    try {
      notify(await put_qb_price({ ...form, quote: form.quote || data.home }));
      selected = form.currency.trim().toUpperCase();
      form = { date: today, currency: "", price: "", quote: "" };
      router.reload();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }

  async function remove(entry_hash: string) {
    try {
      notify(await delete_qb_price(entry_hash));
      router.reload();
    } catch (error) {
      notify_err(error);
    }
  }
</script>

<p class="intro muted">
  Your home currency is <strong>{data.home}</strong>. When you pay or hold money
  in another currency, or own investments, record its price here so reports can
  convert it; without a price, reports leave those amounts out.
</p>

<div class="cards">
  <div class="qb-card stat">
    <span>Home currency</span><strong>{data.home}</strong>
  </div>
  <div class="qb-card stat">
    <span>Other currencies used</span><strong>{used.length}</strong>
  </div>
  <div class="qb-card stat">
    <span>Need a price</span>
    <strong class:bad={needing.length > 0}>{needing.length}</strong>
  </div>
  <div class="qb-card stat">
    <span>Prices recorded</span><strong>{data.prices.length}</strong>
  </div>
</div>

{#if data.currencies.length === 0}
  <div class="qb-card empty">
    <span class="big-icon"><Icon name="coins" size={28} /></span>
    <h2>Everything is in {data.home}</h2>
    <p class="muted">
      Nothing needs a price. Add one when you start paying in another currency
      (a hotel in euros, a supplier in pounds) or buy investments.
    </p>
  </div>
{:else}
  <div class="qb-card table-card">
    <table>
      <thead>
        <tr>
          <th>Currency</th>
          <th class="num">Used in</th>
          <th>Last used</th>
          <th class="num">Latest price</th>
          <th>Change</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each data.currencies as c (c.currency)}
          <tr
            class:active={c.currency === shown}
            onclick={() => (selected = c.currency)}
          >
            <td>
              <strong>{c.currency}</strong>
              {#if c.name}<span class="muted"> {c.name}</span>{/if}
              {#if c.needs_price}
                <span class="badge bad">Needs a price</span>
              {/if}
            </td>
            <td class="num"
              >{c.postings ? `${c.postings.toString()} postings` : "—"}</td
            >
            <td>{c.last_used ? short_date(c.last_used) : "—"}</td>
            <td class="num">
              {#if c.latest}
                {fmt(c.latest.price)}
                {c.latest.quote}
                <span class="muted sub">{short_date(c.latest.date)}</span>
              {:else}
                —
              {/if}
            </td>
            <td class="muted">
              {c.latest && c.previous
                ? change_text(c.latest.price, c.previous.price, "")
                : ""}
            </td>
            <td class="actions">
              <button
                type="button"
                class={c.needs_price
                  ? "qb-primary small"
                  : "qb-secondary small"}
                onclick={(e) => {
                  e.stopPropagation();
                  prefill(c.currency);
                }}>Add price</button
              >
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<div class="grid">
  <form id="price-form" class="qb-card add" onsubmit={add}>
    <h3>Add a price</h3>
    <p class="muted small">
      For example, one EUR cost 1.08 {data.home} on Jan 31. Your bank statement or
      the rate on the payment date is fine for bookkeeping.
    </p>
    <div class="fields">
      <label>
        <span class="cap">Date</span>
        <input type="date" bind:value={form.date} required />
      </label>
      <label>
        <span class="cap">One unit of</span>
        <input
          list="qb-currencies"
          bind:value={form.currency}
          placeholder="EUR"
          required
        />
        <datalist id="qb-currencies">
          {#each data.currencies as c (c.currency)}<option value={c.currency}
            ></option>{/each}
        </datalist>
      </label>
      <label>
        <span class="cap">Costs</span>
        <input
          inputmode="decimal"
          bind:value={form.price}
          placeholder="1.08"
          required
        />
      </label>
      <label>
        <span class="cap">In</span>
        <input bind:value={form.quote} placeholder={data.home} />
      </label>
    </div>
    <button type="submit" class="qb-primary" disabled={busy}>Add price</button>
  </form>

  {#if shown}
    <div class="qb-card history">
      <h3>{shown} price history</h3>
      {#if history.length > 1}
        <TrendChart
          labels={history.map((p) => short_date(p.date))}
          values={{ price: history.map((p) => p.price) }}
          series={[
            {
              key: "price",
              label: `${shown} in ${quote}`,
              color: "#2563eb",
              kind: "line",
            },
          ]}
          currency={quote}
          format={(n: number) => `${fmt(n)} ${quote}`}
          height={200}
          zero={false}
        />
      {/if}
      {#if history.length}
        <table>
          <tbody>
            {#each history.toReversed() as p (p.entry_hash)}
              <tr>
                <td>{short_date(p.date)}</td>
                <td class="num">{fmt(p.price)} {p.quote}</td>
                <td class="actions">
                  <button
                    type="button"
                    class="link"
                    onclick={async () => remove(p.entry_hash)}>Delete</button
                  >
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {:else}
        <p class="muted">No prices for {shown} yet.</p>
      {/if}
    </div>
  {/if}
</div>

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

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
    gap: 0.8rem;
    margin-bottom: 1rem;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .stat span {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .stat strong {
    font-size: 1.4rem;
    font-weight: 650;
  }

  .bad {
    color: var(--error);
  }

  .empty {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    align-items: center;
    padding: 2rem 1rem;
    margin-bottom: 1rem;
    text-align: center;
  }

  .empty h2 {
    margin: 0;
    font-size: 1.15rem;
  }

  .big-icon {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  .table-card {
    padding: 0;
    margin-bottom: 1rem;
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
    vertical-align: top;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-weight: 500;
    color: var(--text-color-lighter);
    text-align: left;
    background: var(--background-darker);
  }

  tbody tr {
    cursor: pointer;
  }

  tr.active td {
    background: var(--qb-accent-soft);
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }

  .sub {
    display: block;
    font-size: 0.8em;
  }

  .badge {
    display: inline-block;
    padding: 0 0.5em;
    margin-left: 0.4em;
    font-size: 0.75em;
    font-weight: 600;
    border: 1px solid currentcolor;
    border-radius: 999px;
  }

  .actions {
    text-align: right;
    white-space: nowrap;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr));
    gap: 1rem;
  }

  h3 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }

  .fields {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 8rem), 1fr));
    gap: 0.6rem;
    margin: 0.6rem 0 0.9rem;
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

  .link {
    padding: 0;
    font-weight: 600;
    color: var(--error);
    background: none;
  }

  .history table td {
    cursor: default;
  }
</style>
