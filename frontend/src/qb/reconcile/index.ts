import { Route } from "../../reports/route.ts";
import type { QbAccountOverview, QbReconcile } from "../api.ts";
import { get_qb_accounts_overview, get_qb_reconcile } from "../api.ts";
import Reconcile from "./Reconcile.svelte";

export interface ReconcileProps {
  accounts: QbAccountOverview[];
  account_name: string;
  /** Statement ending date and balance (as typed); both set while ticking. */
  end_date: string;
  ending: string;
  rec: QbReconcile | null;
}

export const qb_reconcile = new Route<ReconcileProps>(
  "qb_reconcile",
  Reconcile,
  async (url) => {
    const param = (name: string) => url.searchParams.get(name) ?? "";
    const account_name = param("account_name");
    const end_date = param("end_date");
    const ending = param("ending");
    const ticking = end_date !== "" && ending !== "";
    const [accounts, rec] = await Promise.all([
      get_qb_accounts_overview(),
      account_name
        ? get_qb_reconcile({ account_name, end_date: ticking ? end_date : "" })
        : null,
    ]);
    return { accounts, account_name, end_date, ending, rec };
  },
  ({ account_name }) =>
    account_name ? `Reconcile: ${account_name}` : "Reconcile",
);
