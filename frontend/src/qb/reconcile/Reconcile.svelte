<!--
  qb-fork: Reconcile. Compare a bank or card account with its statement:
  enter the statement's ending date and balance, tick each transaction that
  is on the statement, and finish when the difference is zero.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { notify, notify_err } from "../../notifications.ts";
  import { router } from "../../router.ts";
  import { put_qb_reconcile } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import {
    cents,
    cents_string,
    difference,
    parse_amount,
    statement_sign,
  } from "./helpers.ts";
  import type { ReconcileProps } from "./index.ts";

  let { accounts, account_name, end_date, ending, rec }: ReconcileProps =
    $props();

  /** Last day of the previous month, the usual statement date. */
  function last_month_end(): string {
    const now = new Date();
    const d = new Date(now.getFullYear(), now.getMonth(), 0);
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${d.getFullYear().toString()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  // Start form.
  let form_date = $state("");
  let form_ending = $state("");
  // Ticked transactions (entry hashes).
  let ticked = $state<string[]>([]);
  let busy = $state(false);
  /** Set once finished: what was reconciled. */
  let done = $state("");

  $effect.pre(() => {
    form_date = end_date || last_month_end();
    form_ending = ending;
    ticked = [];
    done = "";
  });

  let sign = $derived(statement_sign(account_name));
  let is_card = $derived(sign === -1);
  let currency = $derived(rec?.currency ?? "USD");
  /** Statement ending balance in ledger-sign cents (null while invalid). */
  let ending_cents = $derived.by(() => {
    const parsed = parse_amount(ending);
    return parsed === null ? null : parsed * sign;
  });
  let ticking = $derived(
    rec !== null && end_date !== "" && ending_cents !== null,
  );
  let beginning = $derived(cents(rec?.beginning_balance ?? 0));
  let ticked_amounts = $derived(
    (rec?.rows ?? [])
      .filter((r) => ticked.includes(r.entry_hash))
      .map((r) => cents(r.amount)),
  );
  let diff = $derived(difference(ending_cents ?? 0, beginning, ticked_amounts));
  let cleared = $derived(
    ticked_amounts.reduce((sum, amount) => sum + amount, beginning),
  );
  let columns = $derived(
    is_card
      ? { down: "Charges", up: "Payments" }
      : { down: "Payments", up: "Deposits" },
  );
  let form_problem = $derived(
    !account_name
      ? "Choose an account."
      : !form_date
        ? "Enter the statement ending date."
        : parse_amount(form_ending) === null
          ? "Enter the ending balance from the statement, e.g. 1,234.56."
          : "",
  );

  /** Show a ledger-sign cents amount as the statement prints it. */
  const show = (value: number) => money((value * sign) / 100 + 0, currency);

  function go(params: Record<string, string>) {
    const url = new URL(window.location.href);
    for (const name of ["account_name", "end_date", "ending"]) {
      url.searchParams.delete(name);
    }
    for (const [name, value] of Object.entries(params)) {
      if (value) {
        url.searchParams.set(name, value);
      }
    }
    router.navigate(url);
  }

  function start(event: SubmitEvent) {
    event.preventDefault();
    if (!form_problem) {
      go({ account_name, end_date: form_date, ending: form_ending });
    }
  }

  function toggle(hash: string) {
    ticked = ticked.includes(hash)
      ? ticked.filter((h) => h !== hash)
      : [...ticked, hash];
  }

  async function finish() {
    if (ending_cents === null) {
      return;
    }
    busy = true;
    try {
      const res = await put_qb_reconcile({
        account_name,
        end_date,
        ending_balance: cents_string(ending_cents),
        entry_hashes: ticked,
      });
      done =
        `${res.reconciled.toString()} transactions marked reconciled.` +
        (res.balance_assertion
          ? " A balance check was added, so Favabooks will warn you if a later edit changes this balance."
          : "");
      notify("Reconciliation saved.");
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }
</script>

{#if !ticking}
  <p class="explain">
    Reconciling checks your books against a bank or card statement. Enter the
    statement's ending date and balance, then tick each transaction that appears
    on the statement. When the <strong>difference</strong> is
    {money(0, currency)}, your books match the bank.
  </p>

  <form class="qb-card start" onsubmit={start}>
    <label>
      <span class="cap">Account</span>
      <select
        value={account_name}
        onchange={(e) => {
          go({ account_name: e.currentTarget.value });
        }}
      >
        {#if !account_name}<option value="">Choose an account…</option>{/if}
        {#each accounts as a (a.account)}
          <option value={a.account}>{a.account}</option>
        {/each}
      </select>
    </label>
    {#if rec}
      <label>
        <span class="cap">Statement ending date</span>
        <input type="date" bind:value={form_date} required />
      </label>
      <label>
        <span class="cap"
          >{is_card
            ? "Statement balance (amount you owe)"
            : "Statement ending balance"}</span
        >
        <input
          type="text"
          inputmode="decimal"
          placeholder="0.00"
          bind:value={form_ending}
          required
        />
      </label>
      <div class="info">
        <span class="cap">Beginning balance</span>
        <strong>{show(beginning)}</strong>
        <span class="muted"
          >{rec.history.length
            ? "From your last reconciliation"
            : "First reconciliation: starts at zero"}</span
        >
      </div>
      <div class="go">
        <button type="submit" class="qb-primary" disabled={!!form_problem}>
          Start reconciling
        </button>
        {#if form_problem}<span class="muted">{form_problem}</span>{/if}
      </div>
    {/if}
  </form>

  {#if rec}
    <h3>Past reconciliations</h3>
    {#if rec.history.length}
      <ul class="history">
        {#each rec.history as h (h.comment)}
          <li>
            <Icon name="circle-check" size={15} />
            <span>{short_date(h.date)}</span>
            <span class="muted">{h.comment}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="muted">This account hasn't been reconciled yet.</p>
    {/if}
  {/if}
{:else if done}
  <div class="qb-card finished">
    <span class="big-icon"><Icon name="circle-check" size={28} /></span>
    <h2>
      {account_name} is reconciled through {short_date(
        new Date(`${end_date}T00:00Z`),
      )}
    </h2>
    <p class="muted">{done}</p>
    <div class="actions">
      <a
        class="button qb-primary"
        href={$url_for("qb_reconcile/", { account_name })}
        >Reconcile next statement</a
      >
      <a class="link" href={$url_for("qb_register/", { account_name })}
        >Open register</a
      >
    </div>
  </div>
{:else if rec}
  <div class="summary qb-card">
    <div>
      <span class="cap">Statement ending balance</span>
      <strong>{show(ending_cents ?? 0)}</strong>
    </div>
    <div class="op">−</div>
    <div>
      <span class="cap">Cleared balance</span>
      <strong>{show(cleared)}</strong>
      <small class="muted"
        >{show(beginning)} beginning + {ticked.length} ticked</small
      >
    </div>
    <div class="op">=</div>
    <div class="diff" class:zero={diff === 0}>
      <span class="cap">Difference</span>
      <strong>{show(diff)}</strong>
    </div>
    <div class="actions">
      <button
        type="button"
        class="qb-primary"
        disabled={diff !== 0 || busy}
        onclick={finish}
      >
        Finish now
      </button>
      <a href={$url_for("qb_reconcile/", { account_name })} class="link"
        >Edit statement info</a
      >
    </div>
  </div>

  <p class="explain">
    {account_name} · statement ending {short_date(
      new Date(`${end_date}T00:00Z`),
    )}. Tick each transaction that is on the statement. Transactions not on it
    yet stay open for next time.
    {#if diff !== 0 && rec.rows.length === ticked.length}
      Everything is ticked but the difference isn't zero: a transaction on the
      statement may be missing from your books, or an amount may differ.
    {/if}
  </p>

  {#if rec.rows.length}
    <div class="qb-card table-card">
      <table>
        <thead>
          <tr>
            <th class="check">
              <input
                type="checkbox"
                aria-label="Tick all"
                checked={ticked.length === rec.rows.length}
                onchange={(e) => {
                  ticked = e.currentTarget.checked
                    ? rec.rows.map((r) => r.entry_hash)
                    : [];
                }}
              />
            </th>
            <th>Date</th>
            <th>Payee</th>
            <th>Description</th>
            <th class="num">{columns.down}</th>
            <th class="num">{columns.up}</th>
          </tr>
        </thead>
        <tbody>
          {#each rec.rows as row (row.entry_hash)}
            {@const on = ticked.includes(row.entry_hash)}
            <tr class:on>
              <td class="check">
                <input
                  type="checkbox"
                  id="r-{row.entry_hash}"
                  checked={on}
                  onchange={() => {
                    toggle(row.entry_hash);
                  }}
                />
              </td>
              <td class="date">
                <label class="row-label" for="r-{row.entry_hash}"
                  >{short_date(row.date)}</label
                >
              </td>
              <td
                ><label class="row-label" for="r-{row.entry_hash}"
                  >{row.payee}</label
                ></td
              >
              <td class="desc">
                <label class="row-label" for="r-{row.entry_hash}"
                  >{row.narration}</label
                >
              </td>
              <td class="num"
                >{row.amount < 0 ? money(-row.amount, currency) : ""}</td
              >
              <td class="num"
                >{row.amount > 0 ? money(row.amount, currency) : ""}</td
              >
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="qb-card muted">
      No open transactions on or before this date. Every transaction is already
      reconciled.
    </p>
  {/if}
{/if}

<style>
  .explain {
    max-width: 60rem;
    margin: 0 0 1rem;
    color: var(--text-color-lighter);
  }

  .muted {
    color: var(--qb-muted);
  }

  .start {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem 1.5rem;
    align-items: flex-end;
    margin-bottom: 1.5rem;
  }

  .start label,
  .info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .cap {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .info strong {
    font-size: 1.2rem;
    font-variant-numeric: tabular-nums;
  }

  .go {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    width: 100%;
  }

  h3 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }

  .history {
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .history li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 0.7rem;
    align-items: center;
    padding: 0.4rem 0;
    border-bottom: 1px solid var(--border-lighter);
  }

  .summary {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem 1.4rem;
    align-items: center;
    margin-bottom: 1rem;
  }

  .summary > div:not(.op, .actions) {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .summary .cap {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .summary strong {
    font-size: 1.4rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .op {
    font-size: 1.4rem;
    color: var(--qb-muted);
  }

  .diff strong {
    color: var(--error);
  }

  .diff.zero strong {
    color: var(--qb-accent);
  }

  .actions {
    display: flex;
    gap: 1rem;
    align-items: center;
    margin-left: auto;
  }

  .finished {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: center;
    padding: 2rem 1rem;
    text-align: center;
  }

  .finished h2 {
    margin: 0;
    font-size: 1.15rem;
  }

  .finished .actions {
    margin: 0.5rem 0 0;
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

  a.button {
    color: var(--button-color);
    background: var(--button-background);
  }

  .link {
    font-weight: 600;
    color: var(--qb-accent);
  }

  .table-card {
    padding: 0;
  }

  table {
    width: 100%;
  }

  .row-label {
    display: block;
    cursor: pointer;
  }

  .check {
    width: 2.5rem;
    text-align: center;
  }

  .date {
    white-space: nowrap;
  }

  .desc {
    white-space: normal;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }

  tr.on {
    background: var(--qb-accent-soft);
  }
</style>
