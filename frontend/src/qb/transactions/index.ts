import { Route } from "../../reports/route.ts";
import { get_url_filters } from "../../stores/filters.ts";
import type { QbTransactions } from "../api.ts";
import { get_qb_transactions } from "../api.ts";
import type { Period } from "../docs/periods.ts";
import { period_from_url } from "../docs/periods.ts";
import Transactions from "./Transactions.svelte";

export interface TransactionsProps {
  search: string;
  kind: string;
  result: QbTransactions;
  today: Date;
  period: Period;
}

export const qb_transactions = new Route<TransactionsProps>(
  "qb_transactions",
  Transactions,
  async (url) => {
    const search = url.searchParams.get("search") ?? "";
    const kind = url.searchParams.get("kind") ?? "";
    const { time, account, filter } = get_url_filters(url);
    const { today, period } = period_from_url(url);
    const result = await get_qb_transactions({
      search,
      kind,
      time,
      account,
      filter,
      start: period.start,
      end: period.end,
    });
    return { search, kind, result, today, period };
  },
  () => "All transactions",
);
