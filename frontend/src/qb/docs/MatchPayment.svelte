<!--
  qb-fork: match an invoice or bill to the deposit or payment that settled
  it. That transaction's category moves to Accounts Receivable/Payable.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import ModalBase from "../../modals/ModalBase.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import type { QbDoc, QbPayment } from "../api.ts";
  import { get_qb_doc_payments, put_qb_doc_payment } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import { leaf } from "../transactions/helpers.ts";
  import type { SideText } from "./sides.ts";

  let {
    text,
    doc,
    onclose,
    ondone,
  }: {
    text: SideText;
    doc: QbDoc;
    onclose: () => void;
    ondone: () => void;
  } = $props();

  let payments = $state<QbPayment[] | null>(null);
  let busy = $state(false);

  $effect(() => {
    get_qb_doc_payments(text.side, doc.key).then(
      (found) => {
        payments = found;
      },
      (error: unknown) => {
        notify_err(error);
        payments = [];
      },
    );
  });

  async function match(payment: QbPayment) {
    busy = true;
    try {
      notify(await put_qb_doc_payment(text.side, doc.key, payment.entry_hash));
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
      {text.docs_title.slice(0, -1)}
      <strong>{doc.number}</strong>
      {text.side === "invoice" ? "for" : "from"}
      {doc.party}:
      <strong>{money(doc.balance, doc.currency)}</strong> still due. Pick the
      {text.payment} that paid it. {text.match_intro}
    </p>
    {#if payments === null}
      <p class="muted">Looking for {text.payment}s…</p>
    {:else if payments.length === 0}
      <p class="empty">
        No matching {text.payment}s yet.
        <a href={$url_for("import/")}>{text.match_empty}</a>
      </p>
    {:else}
      <div class="list">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Transaction</th>
              <th>{text.side === "invoice" ? "Into" : "From"}</th>
              <th class="num">Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each payments as p (p.entry_hash)}
              <tr class:exact={p.exact}>
                <td class="nowrap">{short_date(p.date)}</td>
                <td>
                  <strong>{p.payee || p.narration}</strong>
                  {#if p.payee && p.narration}<span class="muted sub"
                      >{p.narration}</span
                    >{/if}
                  <span class="muted sub">now in {leaf(p.category)}</span>
                </td>
                <td>{leaf(p.account)}</td>
                <td class="num">
                  {money(p.amount, p.currency)}
                  {#if p.exact}<span class="tag">Exact amount</span>{/if}
                </td>
                <td>
                  <button
                    type="button"
                    class={p.exact ? "qb-primary small" : "qb-secondary small"}
                    disabled={busy}
                    onclick={async () => match(p)}>Match</button
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
