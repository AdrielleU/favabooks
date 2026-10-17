<!--
  qb-fork: the report center, grouped like QuickBooks' standard reports.
-->
<script lang="ts">
  import { url_for } from "../../helpers.ts";
  import { router } from "../../router.ts";
  import type { QbStatement } from "../api.ts";
  import { pnl_trend } from "../charts/data.ts";
  import TrendChart from "../charts/TrendChart.svelte";
  import { iso } from "../docs/periods.ts";
  import Icon from "../Icon.svelte";
  import type { IconName } from "../icons.ts";

  interface Card {
    title: string;
    text: string;
    report: `${string}/`;
    params?: Record<string, string>;
  }

  let { trend }: { trend: QbStatement } = $props();
  let points = $derived(pnl_trend(trend));

  const last_year = (new Date().getUTCFullYear() - 1).toString();

  const GROUPS: { title: string; icon: IconName; cards: Card[] }[] = [
    {
      title: "Business overview",
      icon: "chart-column",
      cards: [
        {
          title: "Profit and loss",
          text: "Income, expenses and net income for a period.",
          report: "qb_profit_loss/",
        },
        {
          title: "Profit and loss by month",
          text: "Each month side by side, with a total.",
          report: "qb_profit_loss/",
          params: { by: "month", period: "this-year" },
        },
        {
          title: "Profit and loss comparison",
          text: "This period against the one before, with % change.",
          report: "qb_profit_loss/",
          params: { compare: "1", period: "last-year" },
        },
        {
          title: "Balance sheet",
          text: "What you own, what you owe and equity on a date.",
          report: "qb_balance_sheet/",
        },
      ],
    },
    {
      title: "Who owes you",
      icon: "receipt",
      cards: [
        {
          title: "Unpaid invoices and aging",
          text: "Open invoices by days past due.",
          report: "qb_invoices/",
          params: { status: "unpaid" },
        },
        {
          title: "Sales by customer",
          text: "Sales, open and overdue balances per customer.",
          report: "qb_customers/",
        },
      ],
    },
    {
      title: "What you owe and spend",
      icon: "wallet",
      cards: [
        {
          title: "Unpaid bills and aging",
          text: "Open bills by days past due.",
          report: "qb_bills/",
          params: { status: "unpaid" },
        },
        {
          title: "Expenses by vendor",
          text: "Spending per vendor, with usual category.",
          report: "qb_vendors/",
        },
        {
          title: "1099 contractors",
          text: "Vendors paid by bank or check, for 1099-NEC review.",
          report: "qb_vendors/",
          params: { period: last_year },
        },
      ],
    },
    {
      title: "For my accountant",
      icon: "briefcase",
      cards: [
        {
          title: "Trial balance",
          text: "Every account's debit or credit balance.",
          report: "qb_trial_balance/",
        },
        {
          title: "General ledger",
          text: "Every posting by account, with running balances.",
          report: "qb_general_ledger/",
        },
        {
          title: "Transaction list",
          text: "All transactions, filterable and exportable.",
          report: "qb_transactions/",
        },
        {
          title: "Export for CPA",
          text: "The year-end package and a checklist before sending it.",
          report: "qb_exports/",
        },
      ],
    },
    {
      title: "Advanced",
      icon: "sliders-horizontal",
      cards: [
        {
          title: "Query",
          text: "Write your own Beancount query (BQL).",
          report: "query/",
        },
        {
          title: "Fava income statement",
          text: "Fava's original report, with charts and tree tables.",
          report: "income_statement/",
        },
        {
          title: "Fava balance sheet",
          text: "Fava's original report, in any currency.",
          report: "balance_sheet/",
        },
        {
          title: "Statistics",
          text: "Entry counts and postings per account.",
          report: "statistics/",
        },
      ],
    },
  ];
</script>

{#if points.length > 1}
  <section class="qb-card snapshot">
    <h2><Icon name="trending-up" size={18} /> Income and expenses</h2>
    <TrendChart
      labels={points.map((p) => p.label)}
      values={{
        income: points.map((p) => p.income),
        expenses: points.map((p) => p.expenses),
        net: points.map((p) => p.net),
      }}
      series={[
        { key: "income", label: "Income", color: "#10b981", kind: "bar" },
        { key: "expenses", label: "Expenses", color: "#f59e0b", kind: "bar" },
        { key: "net", label: "Net income", color: "#2563eb", kind: "line" },
      ]}
      currency={trend.currency}
      height={220}
      onselect={(i: number) => {
        const p = points[i];
        if (p) {
          router.navigate(
            $url_for("qb_profit_loss/", {
              period: "custom",
              from: p.start ? iso(p.start) : "",
              to: iso(p.end),
            }),
          );
        }
      }}
    />
  </section>
{/if}

{#each GROUPS as group (group.title)}
  <section class="group">
    <h2><Icon name={group.icon} size={18} /> {group.title}</h2>
    <div class="cards">
      {#each group.cards as card (card.title)}
        <a class="qb-card card" href={$url_for(card.report, card.params ?? {})}>
          <strong>{card.title}</strong>
          <span>{card.text}</span>
        </a>
      {/each}
    </div>
  </section>
{/each}

<style>
  .snapshot {
    margin-bottom: 1.5rem;
  }

  .group {
    margin-bottom: 1.5rem;
  }

  h2 {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin: 0 0 0.6rem;
    font-size: 1.05rem;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 15rem), 1fr));
    gap: 0.8rem;
  }

  .card {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    color: inherit;
  }

  .card:hover {
    border-color: var(--qb-accent);
  }

  .card span {
    font-size: 0.9em;
    color: var(--qb-muted);
  }
</style>
