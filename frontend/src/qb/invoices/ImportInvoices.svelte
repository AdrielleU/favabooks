<!--
  qb-fork: import invoices from a CSV export (Stripe, QuickBooks, FreshBooks,
  Wave, a spreadsheet). Columns are matched by name and can be changed;
  invoices already in the books are skipped.
-->
<script lang="ts">
  import ModalBase from "../../modals/ModalBase.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import { accounts } from "../../stores/index.ts";
  import { name_assets } from "../../stores/options.ts";
  import type { QbInvoicePreview } from "../api.ts";
  import {
    put_qb_invoice_csv_import,
    put_qb_invoice_csv_preview,
  } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import { CSV_FIELDS } from "./helpers.ts";

  let {
    income_accounts,
    ar_account,
    onclose,
    ondone,
  }: {
    income_accounts: string[];
    ar_account: string;
    onclose: () => void;
    ondone: () => void;
  } = $props();

  let filename = $state("");
  let content = $state("");
  let preview = $state<QbInvoicePreview | null>(null);
  let mapping = $state<Record<string, string>>({});
  let income_account = $state("");
  let record_payments = $state(false);
  let payment_account = $state("");
  let busy = $state(false);

  $effect.pre(() => {
    if (!income_account) {
      income_account = income_accounts[0] ?? "";
    }
  });

  let asset_accounts = $derived(
    $accounts.filter(
      (a) => a.startsWith(`${$name_assets}:`) && a !== ar_account,
    ),
  );
  let new_rows = $derived(preview?.rows.filter((r) => r.state === "new") ?? []);
  let paid_rows = $derived(new_rows.filter((r) => r.paid > 0));
  let missing = $derived(
    CSV_FIELDS.filter(
      ([field, , required]) => required && (mapping[field] ?? "") === "",
    ).map(([, label]) => label),
  );

  async function load(mapping_override: Record<string, string> | null) {
    busy = true;
    try {
      preview = await put_qb_invoice_csv_preview(content, mapping_override);
      mapping = { ...preview.mapping };
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }

  async function pick(file: File | undefined) {
    if (file === undefined) {
      return;
    }
    filename = file.name;
    content = await file.text();
    await load(null);
    if (!payment_account) {
      payment_account =
        asset_accounts.find((a) => /stripe/i.test(a)) ??
        asset_accounts[0] ??
        "";
    }
  }

  async function save() {
    busy = true;
    try {
      const res = await put_qb_invoice_csv_import({
        content,
        mapping,
        income_account,
        payment_account: record_payments ? payment_account : "",
      });
      notify(
        `Imported ${res.invoices.toString()} invoice${res.invoices === 1 ? "" : "s"}` +
          (res.payments ? ` and ${res.payments.toString()} payments.` : "."),
      );
      ondone();
    } catch (error) {
      notify_err(error);
    } finally {
      busy = false;
    }
  }

  const STATE_LABEL: Record<string, string> = {
    new: "Will import",
    duplicate: "Already in books",
    skipped: "Skipped",
    invalid: "Can't read",
  };
</script>

<ModalBase shown={true} close_handler={onclose}>
  <div class="dialog">
    <h2>Import invoices</h2>
    {#if !preview}
      <p class="muted">
        Export your invoice list as a CSV file and choose it here. This works
        with Stripe (Invoices → Export), QuickBooks (Sales → Invoices → Export),
        FreshBooks, Wave or any spreadsheet with an invoice number, customer,
        date and total.
      </p>
      <label class="file">
        <input
          type="file"
          accept=".csv,text/csv"
          onchange={async (e) => pick(e.currentTarget.files?.[0])}
        />
      </label>
      <p class="muted small">
        Invoices already in your books (for example Stripe payments imported
        with their invoice number) are skipped automatically.
      </p>
    {:else}
      <p class="muted">
        <strong>{filename}</strong>: {preview.rows.length} rows,
        <strong>{new_rows.length}</strong> new.
        <button
          type="button"
          class="link"
          onclick={() => {
            preview = null;
          }}>Choose another file</button
        >
      </p>

      <h3>Columns</h3>
      <div class="mapping">
        {#each CSV_FIELDS as [field, label, required] (field)}
          <label>
            <span>{label}{required ? " *" : ""}</span>
            <select
              value={mapping[field] ?? ""}
              onchange={async (e) => {
                const value = e.currentTarget.value;
                const next = Object.fromEntries(
                  Object.entries(mapping).filter(([f]) => f !== field),
                );
                if (value) {
                  next[field] = value;
                }
                await load(next);
              }}
            >
              <option value="">(none)</option>
              {#each preview.header as column (column)}
                <option value={column}>{column}</option>
              {/each}
            </select>
          </label>
        {/each}
      </div>

      <div class="rows">
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Customer</th>
              <th>Date</th>
              <th>Due</th>
              <th class="num">Total</th>
              <th class="num">Paid</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each preview.rows as r (r.line)}
              <tr class={r.state}>
                <td>{r.number}</td>
                <td>{r.customer}</td>
                <td class="nowrap">{r.date ? short_date(r.date) : ""}</td>
                <td class="nowrap">{r.due ? short_date(r.due) : ""}</td>
                <td class="num"
                  >{r.amount === null
                    ? ""
                    : money(r.amount, r.currency || "USD")}</td
                >
                <td class="num"
                  >{r.paid ? money(r.paid, r.currency || "USD") : ""}</td
                >
                <td>
                  <span class="state {r.state}" title={r.problem}
                    >{STATE_LABEL[r.state] ?? r.state}</span
                  >
                  {#if r.problem && r.state !== "duplicate"}<span
                      class="muted small block">{r.problem}</span
                    >{/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="options">
        <label>
          <span>Book the income to</span>
          <select bind:value={income_account}>
            {#each income_accounts as account (account)}
              <option value={account}>{account}</option>
            {/each}
          </select>
        </label>
        {#if paid_rows.length}
          <label class="check">
            <input type="checkbox" bind:checked={record_payments} />
            <span
              >Also record the {paid_rows.length} payment{paid_rows.length === 1
                ? ""
                : "s"} marked paid, into</span
            >
            <select bind:value={payment_account} disabled={!record_payments}>
              {#each asset_accounts as account (account)}
                <option value={account}>{account}</option>
              {/each}
            </select>
          </label>
          <p class="muted small">
            Leave this off if those payments come in through a bank or Stripe
            import; match them on the Invoices page instead, so nothing is
            counted twice.
          </p>
        {/if}
      </div>
    {/if}

    <div class="foot">
      {#if preview && missing.length}
        <span class="warn">Choose a column for {missing.join(", ")}.</span>
      {/if}
      <button type="button" class="qb-secondary" onclick={onclose}
        >Cancel</button
      >
      {#if preview}
        <button
          type="button"
          class="qb-primary"
          disabled={busy ||
            !new_rows.length ||
            missing.length > 0 ||
            !income_account}
          onclick={save}
        >
          Import {new_rows.length} invoice{new_rows.length === 1 ? "" : "s"}
        </button>
      {/if}
    </div>
  </div>
</ModalBase>

<style>
  .dialog {
    width: min(60rem, 94vw);
  }

  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.2rem;
  }

  h3 {
    margin: 0.8rem 0 0.4rem;
    font-size: 0.95rem;
  }

  .muted {
    color: var(--qb-muted);
  }

  .small {
    font-size: 0.85em;
  }

  .block {
    display: block;
  }

  .warn {
    color: var(--error);
  }

  .file {
    display: block;
    padding: 1.5rem;
    margin: 0.8rem 0;
    text-align: center;
    border: 2px dashed var(--border);
    border-radius: 10px;
  }

  .link {
    padding: 0;
    margin-left: 0.5rem;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }

  .mapping {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 11rem), 1fr));
    gap: 0.5rem 0.8rem;
  }

  .mapping label,
  .options label {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .mapping span,
  .options span {
    font-size: 0.82rem;
    color: var(--qb-muted);
  }

  .rows {
    max-height: 40vh;
    margin-top: 0.8rem;
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0;
  }

  th,
  td {
    padding: 0.4em 0.6em;
    border-bottom: 1px solid var(--border);
  }

  tr.duplicate td,
  tr.skipped td {
    color: var(--qb-muted);
  }

  .num {
    text-align: right;
    white-space: nowrap;
  }

  .nowrap {
    white-space: nowrap;
  }

  .state {
    padding: 0.05em 0.5em;
    font-size: 0.78em;
    font-weight: 600;
    white-space: nowrap;
    background: var(--background-darker);
    border-radius: 999px;
  }

  .state.new {
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
  }

  .state.invalid {
    color: var(--error);
  }

  .options {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin-top: 1rem;
  }

  .options .check {
    flex-flow: row wrap;
    gap: 0.5rem;
    align-items: center;
  }

  .options .check span {
    font-size: 1em;
    color: var(--text-color);
  }

  .options p {
    margin: 0;
  }

  .foot {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    justify-content: flex-end;
    margin-top: 1.2rem;
  }

  .foot .warn {
    margin-right: auto;
  }
</style>
