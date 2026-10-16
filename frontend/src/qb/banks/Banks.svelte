<script lang="ts">
  import AccountInput from "../../entry-forms/AccountInput.svelte";
  import { url_for } from "../../helpers.ts";
  import { notify } from "../../notifications.ts";
  import type { QbBankFormat, QbBankImports } from "../api.ts";

  let { setup }: { setup: QbBankImports } = $props();

  /** One entry per format key (the first layout) for the picker. */
  let choices = $derived(
    setup.formats.filter(
      (fmt, i) => setup.formats.findIndex((f) => f.key === fmt.key) === i,
    ),
  );
  let label_of = $derived(
    new Map(choices.map((f) => [f.key, `${f.bank}, ${f.kind}`])),
  );

  let key = $state("chase_checking");
  let account = $state("");
  let filename = $state("");
  let payout_bank = $state("Assets:Bank:Checking");
  let skip_stripe = $state<boolean>(false);

  let chosen = $derived(choices.find((f) => f.key === key));
  let has_stripe = $derived(
    setup.importers.some((i) => i.key === "stripe_payouts"),
  );

  const q = (text: string) => JSON.stringify(text);

  let line = $derived.by(() => {
    if (key === "stripe_payouts") {
      return `StripePayouts(${q(account || "Assets:Stripe")}, bank=${q(payout_bank)}),`;
    }
    const args = [q(key), q(account || "Assets:Bank:Checking")];
    if (filename.trim()) {
      args.push(`filename=${q(filename.trim())}`);
    }
    if (skip_stripe) {
      args.push('skip=["STRIPE"]');
    }
    return `BankCSV(${args.join(", ")}),`;
  });

  let whole_file = $derived(
    `from fava.qb_importers import BankCSV, StripePayouts

CONFIG = [
    ${line}
]`,
  );

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      notify("Copied.");
    } catch {
      notify("Couldn't copy; select the text instead.", "warning");
    }
  }

  const recognised_by = (fmt: QbBankFormat) =>
    fmt.columns.length
      ? fmt.columns.join(", ")
      : "No header row: date, amount, *, check, description";
</script>

<div class="grid">
  <section class="qb-card">
    <h3>Your bank imports</h3>
    {#each setup.errors as error (error)}
      <p class="error">{error}</p>
    {/each}
    {#if setup.config_file}
      {#if setup.importers.length}
        <table>
          <thead>
            <tr><th>Account</th><th>Format</th></tr>
          </thead>
          <tbody>
            {#each setup.importers as importer (importer.name)}
              <tr>
                <td>{importer.account || "—"}</td>
                <td>
                  {label_of.get(importer.key) ??
                    (importer.key === "stripe_payouts"
                      ? "Stripe payouts"
                      : importer.name)}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {:else if !setup.errors.length}
        <p class="muted">The import config has no importers yet.</p>
      {/if}
      <dl>
        <dt>Config file</dt>
        <dd><code>{setup.config_file}</code></dd>
        <dt>Drop downloads in</dt>
        <dd>
          {#each setup.import_dirs as dir (dir)}<code>{dir}</code><br />{:else}
            <span class="muted">No import-dirs option set.</span>
          {/each}
        </dd>
      </dl>
      <a class="button" href={$url_for("import/")}>Import files →</a>
    {:else}
      <p>
        No import config yet. Create <code>importers/config.py</code> with the
        snippet on the right, then add to <code>main.beancount</code>:
      </p>
      <pre>2026-01-01 custom "fava-option" "import-config" "importers/config.py"
2026-01-01 custom "fava-option" "import-dirs" "inbox"</pre>
    {/if}
  </section>

  <section class="qb-card">
    <h3>Add a bank account</h3>
    <div class="form">
      <label>
        <span>Bank and account type</span>
        <select bind:value={key}>
          {#each choices as fmt (fmt.key)}
            <option value={fmt.key}>
              {fmt.bank}, {fmt.kind}{fmt.confidence === "unverified"
                ? " (unverified)"
                : ""}
            </option>
          {/each}
        </select>
      </label>
      <label>
        <span
          >{key === "stripe_payouts"
            ? "Stripe balance account"
            : "Ledger account"}</span
        >
        <AccountInput bind:value={account} />
      </label>
      {#if key === "stripe_payouts"}
        <label>
          <span>Payouts land in</span>
          <AccountInput bind:value={payout_bank} />
        </label>
      {:else}
        <label>
          <span>File name contains (optional, e.g. last 4 digits)</span>
          <input type="text" bind:value={filename} placeholder="1234" />
        </label>
        <label class="check">
          <input type="checkbox" bind:checked={skip_stripe} />
          <span class="check-text">
            Leave out Stripe payouts (the Stripe importer books them){#if has_stripe}<em
                >. Recommended: you import Stripe.</em
              >{/if}
          </span>
        </label>
      {/if}
    </div>
    {#if chosen}
      <p class="muted">Download: {chosen.download}</p>
    {/if}
    <p class="label">
      Add this line to <code>CONFIG</code>
      <button type="button" class="small" onclick={async () => copy(line)}
        >Copy</button
      >
    </p>
    <pre>{line}</pre>
    <details>
      <summary>Whole file, for a new config</summary>
      <pre>{whole_file}</pre>
      <button
        type="button"
        class="small"
        onclick={async () => copy(whole_file)}
      >
        Copy
      </button>
    </details>
  </section>
</div>

<section class="qb-card formats">
  <h3>Supported formats</h3>
  <p class="muted">
    Files are recognised by their header row, not their name. Every import lands
    in <a href={$url_for("qb_review/")}>For review</a>. A statement balance
    check is added when the file has a running balance, so add an opening
    balance before the first import. Unverified formats have no published
    sample: check the first import, and tell apart look-alike layouts
    (Amex/Relay, Bluevine/Novo) with the file-name option.
  </p>
  <div class="scroll">
    <table>
      <thead>
        <tr>
          <th>Bank</th>
          <th>Account type</th>
          <th>Key</th>
          <th>Download in online banking</th>
          <th>Recognised by columns</th>
          <th>Amounts</th>
          <th>Balance</th>
        </tr>
      </thead>
      <tbody>
        {#each setup.formats as fmt, i (`${fmt.key}-${i.toString()}`)}
          <tr>
            <td>
              <strong>{fmt.bank}</strong>
              {#if fmt.confidence === "unverified"}
                <span class="badge" title="No published sample header"
                  >unverified</span
                >
              {/if}
            </td>
            <td>{fmt.kind}</td>
            <td><code>{fmt.key}</code></td>
            <td>{fmt.download}</td>
            <td class="cols">{recognised_by(fmt)}</td>
            <td>{fmt.amounts}</td>
            <td class="center">{fmt.has_balance ? "✓" : ""}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr));
    gap: 1rem;
    align-items: start;
    margin-bottom: 1rem;
  }

  h3 {
    margin: 0 0 0.75rem;
    font-size: 1em;
    font-weight: 500;
  }

  .muted,
  dt {
    color: var(--text-color-lightest);
  }

  .error {
    color: var(--error);
  }

  table {
    --table-background-even: transparent;

    width: 100%;
    margin: 0 0 0.75rem;
    border: none;
  }

  th,
  td {
    padding: 0.35em 0.5em;
    vertical-align: top;
    border: none;
    border-bottom: 1px solid var(--border);
  }

  th {
    font-weight: 500;
    color: var(--text-color-lighter);
    text-align: left;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 0.75rem;
    margin: 0 0 0.9rem;
    font-size: 0.9em;
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .form {
    display: grid;
    gap: 0.6rem;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  label span {
    font-size: 0.85em;
    color: var(--text-color-lighter);
  }

  label.check {
    flex-direction: row;
    gap: 0.4rem;
    align-items: center;
    font-size: 0.9em;
  }

  label .check-text {
    font-size: 1em;
    color: inherit;
  }

  .check-text em {
    font-style: normal;
    color: var(--text-color-lightest);
  }

  .label {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin: 0.9rem 0 0.3rem;
    font-weight: 500;
  }

  pre {
    padding: 0.6em 0.8em;
    margin: 0 0 0.5rem;
    overflow-x: auto;
    font-size: 0.85em;
    background: var(--code-background);
    border-radius: 4px;
  }

  button.small {
    padding: 0.1em 0.7em;
    font-size: 0.85em;
  }

  a.button {
    display: inline-block;
    padding: 0.3em 1em;
    color: var(--button-color);
    background: var(--button-background);
    border-radius: 4px;
  }

  .scroll {
    overflow-x: auto;
  }

  .formats td {
    font-size: 0.9em;
    white-space: normal;
  }

  .cols {
    max-width: 18rem;
    color: var(--text-color-lighter);
  }

  .center {
    text-align: center;
  }

  .badge {
    display: inline-block;
    padding: 0 0.4em;
    margin-left: 0.3em;
    font-size: 0.75em;
    color: var(--text-color);
    background: color-mix(in srgb, var(--warning) 45%, transparent);
    border-radius: 3px;
  }
</style>
