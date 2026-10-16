<!--
  qb-fork: the "Add account" wizard on the Bank & card accounts page.
  Bank → Account details → Statement file (column mapping for other banks)
  → Review & save. Saves the connection; nothing to copy or paste.
-->
<script lang="ts">
  import { put_upload_import_file } from "../../api/index.ts";
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import ModalBase from "../../modals/ModalBase.svelte";
  import { notify_err } from "../../notifications.ts";
  import { accounts_set } from "../../stores/index.ts";
  import type { QbConnection, QbImportSetup, QbPreview } from "../api.ts";
  import {
    get_qb_import_setup,
    put_qb_connection,
    put_qb_connection_preview,
  } from "../api.ts";
  import { money, short_date } from "../format.ts";
  import Icon from "../Icon.svelte";
  import {
    DATE_FORMATS,
    guess_roles,
    layout_from_roles,
    ROLES,
    type Role,
    roles_problem,
    suggest_account,
  } from "./helpers.ts";

  const CUSTOM = "__custom__";

  interface Props {
    setup: QbImportSetup;
    /** Connection being edited, and its bank's name. */
    editing?: { connection: QbConnection; bank: string } | null;
    /** Inbox file to start from ("Set up account for this file"). */
    file?: string | null;
    onclose: () => void;
    onsaved: (name: string) => void;
  }

  let {
    setup,
    editing = null,
    file = null,
    onclose,
    onsaved,
  }: Props = $props();

  // svelte-ignore state_referenced_locally
  const start = editing?.connection;
  // svelte-ignore state_referenced_locally
  let inbox = $state(setup.inbox);
  let step = $state(start ? 2 : 1);
  let search = $state("");
  // svelte-ignore state_referenced_locally
  let bank = $state(
    editing
      ? editing.connection.kind === "custom"
        ? CUSTOM
        : editing.bank
      : "",
  );
  let format_key = $state(start?.format ?? "");
  let name = $state(start?.name ?? "");
  let last4 = $state(start?.filename ?? "");
  let account = $state(start?.account ?? "");
  const saved_payout = start?.payout_account ?? "";
  let payout_account = $state(
    saved_payout === "" ? "Assets:Bank:Checking" : saved_payout,
  );
  let skip_stripe = $state(start?.skip_stripe ?? false);
  let sample = $state("");
  let roles = $state<Role[]>([]);
  let negate = $state(start?.layout?.negate ?? false);
  let date_format = $state(start?.layout?.date_format ?? "");
  let detect_note = $state("");
  let preview = $state<QbPreview | null>(null);
  let saving = $state(false);
  let uploading = $state(false);

  let bank_choice = $derived(setup.banks.find((b) => b.bank === bank));
  let format = $derived(
    bank_choice?.formats.find((f) => f.key === format_key) ??
      bank_choice?.formats[0],
  );
  let kind = $derived(
    bank === "Stripe" ? "stripe" : bank === CUSTOM ? "custom" : "bank",
  );
  let bank_label = $derived(bank === CUSTOM ? "Other bank" : bank);
  let sample_file = $derived(inbox.find((f) => f.filename === sample));
  let header = $derived(sample_file?.header ?? []);
  let mapping_problem = $derived(
    kind === "custom" && sample_file ? roles_problem(roles) : "",
  );
  let layout = $derived(
    kind !== "custom"
      ? null
      : sample_file
        ? layout_from_roles(header, roles, negate, date_format)
        : (start?.layout ?? null),
  );
  let draft = $derived<Partial<QbConnection>>({
    id: start?.id ?? "",
    kind,
    account,
    name: name || `${bank_label} ${format?.kind ?? ""}`.trim(),
    format: kind === "bank" ? (format?.key ?? "") : "",
    layout,
    filename: last4.trim(),
    skip_stripe: kind === "stripe" ? false : skip_stripe,
    payout_account: kind === "stripe" ? payout_account : "",
    currency: "USD",
  });
  let suggestion = $derived(
    suggest_account(
      bank === CUSTOM ? name || "Bank" : bank,
      format?.kind ?? "",
      last4,
    ),
  );
  let filtered_banks = $derived(
    setup.banks.filter((b) =>
      b.bank.toLowerCase().includes(search.trim().toLowerCase()),
    ),
  );

  function pick_bank(choice: string) {
    bank = choice;
    format_key =
      setup.banks.find((b) => b.bank === choice)?.formats[0]?.key ?? "";
    step = 2;
  }

  /** Use an inbox file: detect its bank, or go to column mapping. */
  function use_file(filename: string) {
    sample = filename;
    const found = inbox.find((f) => f.filename === filename);
    const key = found?.detected[0];
    const match =
      key !== undefined
        ? setup.banks.find((b) => b.formats.some((f) => f.key === key))
        : undefined;
    if (match && key !== undefined) {
      bank = match.bank;
      format_key = key;
      detect_note = `Recognised as ${match.bank}, ${match.formats.find((f) => f.key === key)?.kind ?? ""}.`;
    } else {
      bank = CUSTOM;
      roles = guess_roles(found?.header ?? [], found?.sample ?? []);
      detect_note =
        "We don't recognise this layout yet. Map its columns once and Favabooks remembers it.";
    }
    step = 2;
  }

  // svelte-ignore state_referenced_locally
  if (file !== null && file !== "") {
    use_file(file);
  }

  $effect(() => {
    // New sample for a custom bank: guess the roles from its header.
    if (kind === "custom" && sample_file && roles.length !== header.length) {
      roles = guess_roles(header, sample_file.sample);
    }
  });

  async function upload(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const chosen = input.files?.[0];
    if (!chosen) {
      return;
    }
    uploading = true;
    try {
      const form = new FormData();
      form.append("file", chosen, chosen.name);
      await put_upload_import_file(form);
      inbox = (await get_qb_import_setup()).inbox;
      const added = inbox.find((f) => f.basename === chosen.name);
      if (added) {
        if (step === 1) {
          use_file(added.filename);
        } else {
          sample = added.filename;
        }
      }
    } catch (error) {
      notify_err(error, (e) => `Upload failed: ${e.message}`);
    } finally {
      uploading = false;
      input.value = "";
    }
  }

  // Live preview of the draft on the sample file.
  $effect(() => {
    const draft_account = draft.account ?? "";
    const current = {
      ...draft,
      account: draft_account === "" ? "Assets:Preview" : draft_account,
    };
    if (!sample || step < 3 || mapping_problem) {
      preview = null;
      return;
    }
    const timer = setTimeout(() => {
      put_qb_connection_preview(sample, current).then(
        (result) => {
          preview = result;
        },
        () => {
          preview = null;
        },
      );
    }, 250);
    return () => {
      clearTimeout(timer);
    };
  });

  let step_problem = $derived.by(() => {
    if (step === 2) {
      if (!account.trim()) {
        return "Choose the ledger account to post to.";
      }
      if (
        !/^(Assets|Liabilities|Equity|Income|Expenses)(:[A-Z0-9][\w-]*)+$/.test(
          account.trim(),
        )
      ) {
        return "Account names look like Assets:Bank:Checking (no spaces).";
      }
    }
    if (step === 3 && kind === "custom") {
      if (!sample_file && !start?.layout) {
        return "Choose or upload a statement file to map its columns.";
      }
      return mapping_problem;
    }
    return "";
  });

  async function save() {
    saving = true;
    try {
      await put_qb_connection(draft);
      onsaved(draft.name ?? bank_label);
    } catch (error) {
      notify_err(error, (e) => `Couldn't save: ${e.message}`);
    } finally {
      saving = false;
    }
  }

  const STEPS = ["Bank", "Account details", "Statement file", "Review & save"];
</script>

<ModalBase shown={true} close_handler={onclose}>
  <div class="wizard">
    <div class="wizard-head">
      <h2>
        {start
          ? `Edit ${start.name || bank_label}`
          : "Add a bank or card account"}
      </h2>
      <ol class="stepper">
        {#each STEPS as label, i (label)}
          <li class:done={step > i + 1} class:current={step === i + 1}>
            <span class="step-no">{i + 1}</span>{label}
          </li>
        {/each}
      </ol>
    </div>

    <div class="body">
      {#if step === 1}
        <section class="detect">
          <h3>Have a statement file? We'll recognise the bank.</h3>
          <div class="row">
            {#if inbox.length}
              <select
                onchange={(e) => {
                  use_file(e.currentTarget.value);
                }}
              >
                <option value="">Pick a file in Import files…</option>
                {#each inbox as f (f.filename)}
                  <option value={f.filename}>{f.basename}</option>
                {/each}
              </select>
              <span class="muted">or</span>
            {/if}
            <label class="button qb-secondary upload">
              <Icon name="upload" size={16} />
              {uploading ? "Uploading…" : "Upload a CSV"}
              <input type="file" accept=".csv,.txt" onchange={upload} hidden />
            </label>
          </div>
        </section>
        <h3>Or choose your bank</h3>
        <input
          type="search"
          class="search"
          placeholder="Search banks"
          bind:value={search}
        />
        <div class="tiles">
          {#each filtered_banks as choice (choice.bank)}
            <button
              type="button"
              class="tile"
              onclick={() => {
                pick_bank(choice.bank);
              }}
            >
              <span class="avatar">{choice.bank.slice(0, 1)}</span>
              <strong>{choice.bank}</strong>
              <span class="muted">
                {choice.formats.map((f) => f.kind).join(" · ")}
              </span>
              {#if choice.formats.every((f) => f.confidence === "unverified")}
                <span class="chip warn">unverified layout</span>
              {/if}
            </button>
          {/each}
          <button
            type="button"
            class="tile other"
            onclick={() => {
              pick_bank(CUSTOM);
            }}
          >
            <span class="avatar"
              ><Icon name="sliders-horizontal" size={18} /></span
            >
            <strong>Other bank</strong>
            <span class="muted">Map the columns of any CSV</span>
          </button>
        </div>
      {:else if step === 2}
        {#if detect_note}<p class="note">{detect_note}</p>{/if}
        {#if bank_choice && bank_choice.formats.length > 1}
          <fieldset>
            <legend>Account type</legend>
            {#each bank_choice.formats as f (f.key)}
              <label class="radio">
                <input type="radio" bind:group={format_key} value={f.key} />
                {f.kind}
                {#if f.confidence === "unverified"}<span class="chip warn"
                    >unverified</span
                  >{/if}
              </label>
            {/each}
          </fieldset>
        {/if}
        <label class="field">
          <span>Nickname</span>
          <input
            type="text"
            bind:value={name}
            placeholder={`${bank_label} ${format?.kind ?? ""}`}
          />
        </label>
        {#if kind !== "stripe"}
          <label class="field">
            <span>Last 4 digits (optional)</span>
            <input
              type="text"
              inputmode="numeric"
              maxlength="8"
              bind:value={last4}
              placeholder="1234"
            />
            <small
              >Tells two accounts at the same bank apart: the downloaded file's
              name must contain these digits.</small
            >
          </label>
        {/if}
        <div class="field">
          <span>Post to ledger account</span>
          <AccountInput bind:value={account} />
          {#if account !== suggestion}
            <button
              type="button"
              class="link"
              onclick={() => (account = suggestion)}
            >
              Use {suggestion}
            </button>
          {/if}
          {#if account && !$accounts_set.has(account)}
            <small
              >New account: Favabooks opens it in your ledger when you save.</small
            >
          {/if}
        </div>
        {#if kind === "stripe"}
          <div class="field">
            <span>Payouts land in</span>
            <AccountInput bind:value={payout_account} />
          </div>
        {:else}
          <label class="radio">
            <input type="checkbox" bind:checked={skip_stripe} />
            Leave out Stripe payouts (when Stripe is connected, it books them)
          </label>
        {/if}
      {:else if step === 3}
        <section class="instructions">
          <h3>Get your statement file</h3>
          {#if format?.download}
            <p>
              <Icon name="download" size={16} /> In online banking:
              <strong>{format.download}</strong>
            </p>
          {:else}
            <p>
              In online banking, look for <strong>Download</strong>,
              <strong>Export</strong>
              or <strong>Statements</strong> and choose <strong>CSV</strong>.
            </p>
          {/if}
          <p class="muted">
            Pick a date range that starts at your last import: rows already in
            your books are skipped.
          </p>
        </section>
        <div class="row">
          <select bind:value={sample}>
            <option value=""
              >{kind === "custom"
                ? "Choose a statement file…"
                : "Test with a file (optional)…"}</option
            >
            {#each inbox as f (f.filename)}
              <option value={f.filename}>{f.basename}</option>
            {/each}
          </select>
          <label class="button qb-secondary upload">
            <Icon name="upload" size={16} />
            {uploading ? "Uploading…" : "Upload a CSV"}
            <input type="file" accept=".csv,.txt" onchange={upload} hidden />
          </label>
        </div>

        {#if kind === "custom" && sample_file}
          <h3>Map the columns</h3>
          <div class="mapping">
            <table>
              <thead>
                <tr>
                  {#each header as column, i (i)}
                    <th>
                      <span class="col">{column}</span>
                      <select
                        bind:value={roles[i]}
                        aria-label={`Use ${column} as`}
                      >
                        {#each ROLES as [value, label] (value)}
                          <option {value}>{label}</option>
                        {/each}
                      </select>
                    </th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each sample_file.sample as row, r (r)}
                  <tr>
                    {#each Array.from(header.keys()) as i (i)}
                      <td class:used={roles[i] !== "ignore"}>{row[i] ?? ""}</td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          <div class="options">
            {#if roles.includes("amount")}
              <fieldset>
                <legend>How are amounts shown?</legend>
                <label class="radio"
                  ><input type="radio" bind:group={negate} value={false} /> Negative
                  amounts are money out</label
                >
                <label class="radio"
                  ><input type="radio" bind:group={negate} value={true} /> Positive
                  amounts are money out (typical for cards)</label
                >
              </fieldset>
            {/if}
            <label class="field">
              <span>Date format</span>
              <select bind:value={date_format}>
                {#each DATE_FORMATS as [value, label] (value)}
                  <option {value}>{label}</option>
                {/each}
              </select>
            </label>
          </div>
        {/if}

        {#if preview}
          {#if !preview.matches}
            <p class="bad">
              This file doesn't match {bank_label}'s layout. {preview.problem}
            </p>
          {:else}
            <p class:good={!preview.problem} class:bad={preview.problem}>
              {preview.problem ? "⚠" : "✓"}
              {preview.parsed} of {preview.total} rows read{preview.problem
                ? `. ${preview.problem}`
                : ""}
            </p>
          {/if}
        {/if}
      {:else}
        <dl class="summary">
          <dt>Bank</dt>
          <dd>
            {bank_label}{format && kind === "bank"
              ? `, ${format.kind}`
              : ""}{kind === "custom" ? ", custom column mapping" : ""}
          </dd>
          <dt>Nickname</dt>
          <dd>{draft.name}</dd>
          <dt>Posts to</dt>
          <dd>
            <code>{account}</code>{#if !$accounts_set.has(account)}
              <span class="chip">new account</span>{/if}
          </dd>
          {#if kind === "stripe"}<dt>Payouts land in</dt>
            <dd><code>{payout_account}</code></dd>{/if}
          {#if last4.trim()}<dt>File name contains</dt>
            <dd>{last4.trim()}</dd>{/if}
          {#if skip_stripe && kind !== "stripe"}<dt>Stripe payouts</dt>
            <dd>Left out</dd>{/if}
        </dl>
        {#if preview !== null && preview.matches && preview.rows.length > 0}
          <h3>First rows as they will be imported</h3>
          <table class="preview">
            <tbody>
              {#each preview.rows as row, i (i)}
                <tr>
                  <td>{short_date(row.date)}</td>
                  <td>{row.payee}</td>
                  <td
                    class="num"
                    class:in={row.amount > 0}
                    class:out={row.amount < 0}
                  >
                    {money(row.amount, row.currency || "USD")}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
          <p class="muted">Every imported transaction lands in For review.</p>
        {:else}
          <p class="muted">
            Files from this account will be recognised in Import files once
            saved.
          </p>
        {/if}
      {/if}
    </div>

    <div class="wizard-foot">
      {#if step_problem}<span class="bad">{step_problem}</span>{/if}
      <span class="spacer"></span>
      <button type="button" class="qb-secondary" onclick={onclose}
        >Cancel</button
      >
      {#if step > 1}
        <button type="button" class="qb-secondary" onclick={() => (step -= 1)}
          >Back</button
        >
      {/if}
      {#if step > 1 && step < 4}
        <button
          type="button"
          class="qb-primary"
          disabled={Boolean(step_problem)}
          onclick={() => (step += 1)}>Next</button
        >
      {:else if step === 4}
        <button
          type="button"
          class="qb-primary"
          disabled={saving}
          onclick={save}
        >
          {saving ? "Saving…" : "Save account"}
        </button>
      {/if}
    </div>
  </div>
</ModalBase>

<style>
  .wizard {
    display: flex;
    flex-direction: column;
    width: min(56rem, 92vw);
    max-height: 85vh;
  }

  .wizard-head h2 {
    margin: 0 0 0.75rem;
    font-size: 1.2rem;
  }

  .stepper {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1.2rem;
    padding: 0 0 0.9rem;
    margin: 0;
    list-style: none;
    border-bottom: 1px solid var(--border);
  }

  .stepper li {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    font-size: 0.88rem;
    color: var(--qb-muted);
  }

  .stepper .step-no {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    font-size: 0.75rem;
    font-weight: 600;
    background: var(--background-darker);
    border-radius: 50%;
  }

  .stepper li.current {
    font-weight: 600;
    color: var(--text-color);
  }

  .stepper li.current .step-no,
  .stepper li.done .step-no {
    color: #fff;
    background: var(--qb-accent-strong);
  }

  .body {
    flex: 1;
    padding: 1rem 0;
    overflow: auto;
  }

  h3 {
    margin: 0.4rem 0 0.6rem;
    font-size: 0.98rem;
    font-weight: 600;
  }

  .muted,
  small {
    color: var(--qb-muted);
  }

  .detect {
    padding: 0.8rem 1rem;
    margin-bottom: 1rem;
    background: var(--qb-accent-soft);
    border-radius: var(--qb-radius);
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
  }

  .upload {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
    cursor: pointer;
  }

  .search {
    width: 100%;
    margin-bottom: 0.8rem;
  }

  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
    gap: 0.6rem;
  }

  .tile {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    align-items: flex-start;
    padding: 0.8rem;
    font-weight: normal;
    color: var(--text-color);
    text-align: left;
    background: var(--qb-surface);
    border: 1px solid var(--border);
    border-radius: var(--qb-radius);
  }

  .tile:hover {
    border-color: var(--qb-accent);
  }

  .tile .muted {
    font-size: 0.8rem;
  }

  .avatar {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    margin-bottom: 0.2rem;
    font-weight: 700;
    color: var(--qb-accent);
    background: var(--qb-accent-soft);
    border-radius: 50%;
  }

  .chip {
    padding: 0 0.5rem;
    font-size: 0.72rem;
    background: var(--background-darker);
    border-radius: 999px;
  }

  .chip.warn {
    background: color-mix(in srgb, var(--warning) 45%, transparent);
  }

  fieldset {
    padding: 0;
    margin: 0 0 1rem;
    border: 0;
  }

  legend {
    margin-bottom: 0.3rem;
    font-weight: 600;
  }

  .radio {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin: 0.3rem 0;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-width: 30rem;
    margin-bottom: 1rem;
  }

  .field > span {
    font-weight: 600;
  }

  .link {
    align-self: flex-start;
    padding: 0;
    font-weight: 600;
    color: var(--qb-accent);
    background: none;
  }

  .note {
    padding: 0.6rem 0.9rem;
    background: var(--qb-accent-soft);
    border-radius: 8px;
  }

  .instructions p {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    align-items: center;
    margin: 0.3rem 0;
  }

  .mapping {
    max-width: 100%;
    margin-bottom: 0.8rem;
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  .mapping table {
    --table-background-even: transparent;

    margin: 0;
  }

  .mapping th {
    vertical-align: top;
    background: var(--background-darker);
  }

  .mapping .col {
    display: block;
    margin-bottom: 0.3rem;
    font-weight: 600;
  }

  .mapping td {
    color: var(--qb-muted);
  }

  .mapping td.used {
    color: var(--text-color);
  }

  .options {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem 2rem;
  }

  .good {
    font-weight: 600;
    color: var(--diff-positive);
  }

  .bad {
    font-weight: 600;
    color: var(--error);
  }

  .summary {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.4rem 1rem;
  }

  .summary dt {
    color: var(--qb-muted);
  }

  .summary dd {
    margin: 0;
  }

  .preview {
    --table-background-even: transparent;

    width: 100%;
  }

  .preview .num {
    text-align: right;
  }

  .in {
    color: var(--diff-positive);
  }

  .out {
    color: var(--diff-negative);
  }

  .wizard-foot {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    padding-top: 0.8rem;
    border-top: 1px solid var(--border);
  }

  .spacer {
    flex: 1;
  }
</style>
