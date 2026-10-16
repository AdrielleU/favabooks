<!--
  qb-fork: match an invoice to the deposit that paid it. The deposit's
  income or uncategorized line moves to Accounts Receivable.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import ModalBase from "../../modals/ModalBase.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import type { QbDeposit, QbInvoice } from "../api.ts";
  import { get_qb_invoice_deposits, put_qb_invoice_payment } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import { leaf } from "../transactions/helpers.ts";

  let {
    invoice,
    onclose,
    ondone,
  }: { invoice: QbInvoice; onclose: () => void; ondone: () => void } = $props();

  let deposits = $state<QbDeposit[] | null>(null);
  let busy = $state(false);

  $effect(() => {
    get_qb_invoice_deposits(invoice.number).then(
      (found) => {
        deposits = found;
      },
      (error: unknown) => {
        notify_err(error);
        deposits = [];
      },
    );
  });

  async function match(deposit: QbDeposit) {
    busy = true;
    try {
      notify(await put_qb_invoice_payment(invoice.number, deposit.entry_hash));
      ondone();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }
</script>

<ModalBase shown={true} close_handler={onclose}>
  <div class="dialog">
    <h2>Match a payment</h2>
    <p class="muted">
      Invoice <strong>{invoice.number}</strong> for {invoice.customer}:
      <strong>{money(invoice.balance, invoice.currency)}</strong> still due. Pick
      the deposit that paid it. Its category becomes Accounts Receivable, so the money
      isn't counted as income twice.
    </p>
    {#if deposits === null}
      <p class="muted">Looking for deposits…</p>
    {:else if deposits.length === 0}
      <p class="empty">
        No matching deposits yet. Import the bank or Stripe statement with this
        payment in <a href={$url_for("import/")}>Import files</a>, then come
        back.
      </p>
    {:else}
      <div class="list">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Deposit</th>
              <th>Into</th>
              <th class="num">Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each deposits as d (d.entry_hash)}
              <tr class:exact={d.exact}>
                <td class="nowrap">{short_date(d.date)}</td>
                <td>
                  <strong>{d.payee || d.narration}</strong>
                  {#if d.payee && d.narration}<span class="muted sub"
                      >{d.narration}</span
                    >{/if}
                  <span class="muted sub">now in {leaf(d.category)}</span>
                </td>
                <td>{leaf(d.account)}</td>
                <td class="num">
                  {money(d.amount, d.currency)}
                  {#if d.exact}<span class="tag">Exact amount</span>{/if}
                </td>
                <td>
                  <button
                    type="button"
                    class={d.exact ? "qb-primary small" : "qb-secondary small"}
                    disabled={busy}
                    onclick={async () => match(d)}>Match</button
                  >
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
    <div class="foot">
      <button type="button" class="qb-secondary" onclick={onclose}>Close</button
      >
    </div>
  </div>
</ModalBase>

<style>
  .dialog {
    width: min(48rem, 92vw);
  }

  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.2rem;
  }

  .muted {
    color: var(--qb-muted);
  }

  .empty {
    padding: 1rem;
    background: var(--background-darker);
    border-radius: 8px;
  }

  .list {
    max-height: 50vh;
    overflow: auto;
  }

  table {
    --table-background-even: transparent;

    width: 100%;
  }

  th,
  td {
    padding: 0.5em 0.6em;
    vertical-align: top;
    border-bottom: 1px solid var(--border);
  }

  tr.exact td {
    background: var(--qb-accent-soft);
  }

  .sub {
    display: block;
    font-size: 0.85em;
  }

  .num {
    text-align: right;
    white-space: nowrap;
  }

  .nowrap {
    white-space: nowrap;
  }

  .tag {
    display: block;
    font-size: 0.75em;
    color: var(--qb-accent);
  }

  .small {
    padding: 0.3em 1em;
    font-size: 0.88em;
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    margin-top: 1rem;
  }
</style>
