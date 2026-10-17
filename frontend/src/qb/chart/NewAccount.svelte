<!-- qb-fork: add an account to the chart of accounts. -->
<script lang="ts">
  import ModalBase from "../../modals/ModalBase.svelte";
  import { notify, notify_err } from "../../notifications.ts";
  import type { QbChart } from "../api.ts";
  import { put_qb_account_open } from "../api.ts";
  import { NEW_KINDS, new_account_name } from "./helpers.ts";

  let {
    chart,
    onclose,
    ondone,
  }: { chart: QbChart; onclose: () => void; ondone: () => void } = $props();

  let kind = $state("expense");
  let name = $state("");
  let parent = $state("");
  let date = $state("");
  let busy = $state(false);

  let spec = $derived(NEW_KINDS.find(([k]) => k === kind) ?? NEW_KINDS[0]);
  let root = $derived(chart.roots[spec?.[2] ?? "expenses"] ?? "Expenses");
  let parents = $derived(
    chart.accounts
      .map((a) => a.account)
      .filter((a) => a.startsWith(`${root}:`))
      .flatMap((a) => {
        const parts = a.split(":");
        return parts.slice(2).map((_, i) => parts.slice(0, i + 2).join(":"));
      })
      .filter((a, i, all) => all.indexOf(a) === i)
      .sort(),
  );
  let fixed_name = $derived(
    kind === "receivable"
      ? "AccountsReceivable"
      : kind === "payable"
        ? "AccountsPayable"
        : "",
  );
  let account = $derived(
    new_account_name(root, spec?.[3] ?? "", parent, fixed_name || name),
  );
  let exists = $derived(chart.accounts.some((a) => a.account === account));
  /** Default opening date: when the books' accounts were opened. */
  let first_open = $derived(
    chart.accounts
      .map((a) => a.open_date)
      .filter((d): d is Date => d !== null)
      .sort((a, b) => a.getTime() - b.getTime())[0],
  );
  $effect.pre(() => {
    if (!date) {
      date = (first_open ?? new Date()).toISOString().slice(0, 10);
    }
  });
  let problem = $derived(
    !fixed_name && !name.trim()
      ? "Enter a name."
      : exists
        ? `${account} already exists.`
        : !date
          ? "Enter the opening date."
          : "",
  );

  async function save(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    try {
      notify(
        await put_qb_account_open({
          account,
          date,
          currency: chart.currency,
        }),
      );
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
    <h2>New account</h2>
    <label>
      <span>Account type</span>
      <select
        bind:value={kind}
        onchange={() => {
          parent = "";
        }}
      >
        {#each NEW_KINDS as [key, label] (key)}
          <option value={key}>{label}</option>
        {/each}
      </select>
    </label>
    {#if !fixed_name}
      <label>
        <span>Name</span>
        <input
          bind:value={name}
          placeholder={kind === "bank"
            ? "e.g. Chase Checking"
            : kind === "card"
              ? "e.g. Amex Gold"
              : "e.g. Office Supplies"}
          required
        />
      </label>
      {#if parents.length && kind !== "bank" && kind !== "card"}
        <label>
          <span>Sub-account of (optional)</span>
          <select bind:value={parent}>
            <option value="">(none)</option>
            {#each parents as p (p)}<option value={p}>{p}</option>{/each}
          </select>
        </label>
      {/if}
    {/if}
    <label>
      <span>Opening date</span>
      <input type="date" bind:value={date} required />
      <small class="muted"
        >On or before its first transaction. Your other accounts open on
        {first_open?.toISOString().slice(0, 10) ?? "—"}.</small
      >
    </label>
    <p class="preview">
      Will be added as <code>{account}</code>
    </p>
    <div class="foot">
      {#if problem}<span class="warn">{problem}</span>{/if}
      <button type="button" class="qb-secondary" onclick={onclose}
        >Cancel</button
      >
      <button type="submit" class="qb-primary" disabled={busy || !!problem}>
        Add account
      </button>
    </div>
  </form>
</ModalBase>

<style>
  .dialog {
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    width: min(32rem, 92vw);
  }

  h2 {
    margin: 0;
    font-size: 1.2rem;
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

  .muted {
    color: var(--qb-muted);
  }

  .preview {
    margin: 0;
  }

  .warn {
    margin-right: auto;
    color: var(--error);
  }

  .foot {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    justify-content: flex-end;
  }
</style>
