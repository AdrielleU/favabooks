<!--
  qb-fork: record an invoice sent from somewhere else (a PDF, Word, another
  app), optionally attaching its PDF.
-->
<script lang="ts">
  import { put_add_document } from "../../api/index.ts";
  import ModalBase from "../../modals/ModalBase.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import { documents } from "../../stores/options.ts";
  import type { QbInvoiceForm } from "../api.ts";
  import { put_qb_invoice } from "../api.ts";
  import { add_days } from "./helpers.ts";

  let {
    customers,
    income_accounts,
    ar_account,
    onclose,
    ondone,
  }: {
    customers: string[];
    income_accounts: string[];
    ar_account: string;
    onclose: () => void;
    ondone: () => void;
  } = $props();

  const today = new Date().toISOString().slice(0, 10);

  let form = $state<QbInvoiceForm>({
    customer: "",
    number: "",
    date: today,
    due: add_days(today, 30),
    amount: "",
    income_account: "",
    memo: "",
    email: "",
  });
  let due_touched = $state(false);
  let files = $state<FileList | null>(null);
  let busy = $state(false);

  $effect.pre(() => {
    if (!form.income_account) {
      form.income_account = income_accounts[0] ?? "";
    }
  });

  let problem = $derived(
    !form.customer.trim()
      ? "Enter the customer."
      : !form.number.trim()
        ? "Enter the invoice number."
        : !form.date
          ? "Enter the invoice date."
          : !(Number.parseFloat(form.amount.replace(/[$,]/g, "")) > 0)
            ? "Enter the invoice total."
            : !form.income_account
              ? "Choose the income account."
              : "",
  );

  async function save(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    try {
      const { entry_hash } = await put_qb_invoice(form);
      const file = files?.[0];
      const folder = $documents[0];
      if (file !== undefined && folder !== undefined) {
        const data = new FormData();
        data.set("account", ar_account);
        data.set("hash", entry_hash);
        data.set("folder", folder);
        const name = /^\d{4}-\d{2}-\d{2}/.test(file.name)
          ? file.name
          : `${form.date} ${file.name}`;
        data.set("file", file, name);
        await put_add_document(data);
      }
      notify(`Recorded invoice ${form.number}.`);
      ondone();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }
</script>

<ModalBase shown={true} close_handler={onclose}>
  <form class="dialog" onsubmit={save}>
    <h2>Record an invoice</h2>
    <p class="muted">
      For an invoice you already sent from somewhere else. It's booked as money
      the customer owes you (Accounts Receivable) until you match the payment.
    </p>
    <div class="grid">
      <label class="wide">
        <span>Customer</span>
        <input list="qb-customers" bind:value={form.customer} required />
        <datalist id="qb-customers">
          {#each customers as name (name)}<option value={name}></option>{/each}
        </datalist>
      </label>
      <label>
        <span>Invoice number</span>
        <input bind:value={form.number} placeholder="e.g. 1042" required />
      </label>
      <label>
        <span>Total</span>
        <input
          inputmode="decimal"
          bind:value={form.amount}
          placeholder="0.00"
          required
        />
      </label>
      <label>
        <span>Invoice date</span>
        <input
          type="date"
          bind:value={
            () => form.date,
            (value: string) => {
              form.date = value;
              if (!due_touched) {
                form.due = add_days(value, 30);
              }
            }
          }
          required
        />
      </label>
      <label>
        <span>Due date</span>
        <input
          type="date"
          bind:value={
            () => form.due,
            (value: string) => {
              form.due = value;
              due_touched = true;
            }
          }
        />
      </label>
      <label>
        <span>Income account</span>
        <select bind:value={form.income_account}>
          {#each income_accounts as account (account)}
            <option value={account}>{account}</option>
          {/each}
        </select>
      </label>
      <label>
        <span>Customer email (optional)</span>
        <input type="email" bind:value={form.email} />
      </label>
      <label class="wide">
        <span>What it's for (optional)</span>
        <input bind:value={form.memo} placeholder="e.g. October retainer" />
      </label>
      <label class="wide">
        <span>Invoice PDF (optional)</span>
        <input type="file" accept=".pdf,image/*" bind:files />
      </label>
    </div>
    {#if !income_accounts.length}
      <p class="warn">
        Your ledger has no income accounts yet. Open one (e.g. Income:Services)
        in the Editor first.
      </p>
    {/if}
    <div class="foot">
      {#if problem}<span class="muted">{problem}</span>{/if}
      <button type="button" class="qb-secondary" onclick={onclose}
        >Cancel</button
      >
      <button type="submit" class="qb-primary" disabled={busy || !!problem}>
        Save invoice
      </button>
    </div>
  </form>
</ModalBase>

<style>
  .dialog {
    width: min(40rem, 92vw);
  }

  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.2rem;
  }

  .muted {
    color: var(--qb-muted);
  }

  .warn {
    color: var(--error);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 14rem), 1fr));
    gap: 0.8rem 1rem;
  }

  .wide {
    grid-column: 1 / -1;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  label span {
    font-size: 0.85rem;
    color: var(--qb-muted);
  }

  .foot {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    justify-content: flex-end;
    margin-top: 1.2rem;
  }

  .foot .muted {
    margin-right: auto;
  }
</style>
