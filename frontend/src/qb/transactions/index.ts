import { Route } from "../../reports/route.ts";
import { get_url_filters } from "../../stores/filters.ts";
import type { QbTransactions } from "../api.ts";
import { get_qb_transactions } from "../api.ts";
import Transactions from "./Transactions.svelte";

export interface TransactionsProps {
  search: string;
  kind: string;
  result: QbTransactions;
}

export const qb_transactions = new Route<TransactionsProps>(
  "qb_transactions",
  Transactions,
  async (url) => {
    const search = url.searchParams.get("search") ?? "";
    const kind = url.searchParams.get("kind") ?? "";
    const { time, account, filter } = get_url_filters(url);
    const result = await get_qb_transactions({
      search,
      kind,
      time,
      account,
      filter,
    });
    return { search, kind, result };
  },
  () => "All transactions",
);
