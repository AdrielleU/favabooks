import { Route } from "../../reports/route.ts";
import {
  get_qb_balance_sheet,
  get_qb_general_ledger,
  get_qb_profit_loss,
  get_qb_trial_balance,
} from "../api.ts";
import { period_from_url } from "../docs/periods.ts";
import BalanceSheet from "./BalanceSheet.svelte";
import GeneralLedger from "./GeneralLedger.svelte";
import ProfitLoss from "./ProfitLoss.svelte";
import ReportsHome from "./ReportsHome.svelte";
import TrialBalance from "./TrialBalance.svelte";

const param = (url: URL, name: string) => url.searchParams.get(name) ?? "";

export const qb_reports = new Route(
  "qb_reports",
  ReportsHome,
  () => ({}),
  () => "Reports",
);

export const qb_profit_loss = new Route(
  "qb_profit_loss",
  ProfitLoss,
  async (url) => {
    const { today, period } = period_from_url(url);
    const by = param(url, "by") || "total";
    const compare = param(url, "compare") === "1";
    const statement = await get_qb_profit_loss({
      start: period.start,
      end: period.end,
      by,
      compare: compare ? "1" : "",
    });
    return { statement, period, today, by, compare };
  },
  () => "Profit and loss",
);

export const qb_balance_sheet = new Route(
  "qb_balance_sheet",
  BalanceSheet,
  async (url) => {
    const { today } = period_from_url(url);
    const compare = param(url, "compare") === "1";
    const statement = await get_qb_balance_sheet({
      as_of: param(url, "as_of"),
      compare: compare ? "1" : "",
    });
    return { statement, today, compare };
  },
  () => "Balance sheet",
);

export const qb_trial_balance = new Route(
  "qb_trial_balance",
  TrialBalance,
  async (url) => ({
    data: await get_qb_trial_balance(param(url, "as_of")),
    today: period_from_url(url).today,
  }),
  () => "Trial balance",
);

export const qb_general_ledger = new Route(
  "qb_general_ledger",
  GeneralLedger,
  async (url) => {
    const { today, period } = period_from_url(url);
    const account = param(url, "account_name");
    const data = await get_qb_general_ledger({
      start: period.start,
      end: period.end,
      account,
    });
    return { data, period, today, account };
  },
  () => "General ledger",
);
