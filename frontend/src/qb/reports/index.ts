import { Route } from "../../reports/route.ts";
import {
  get_qb_balance_sheet,
  get_qb_balance_trend,
  get_qb_general_ledger,
  get_qb_profit_loss,
  get_qb_trial_balance,
} from "../api.ts";
import { trend_by } from "../charts/data.ts";
import { iso, period_from_url } from "../docs/periods.ts";
import BalanceSheet from "./BalanceSheet.svelte";
import GeneralLedger from "./GeneralLedger.svelte";
import ProfitLoss from "./ProfitLoss.svelte";
import ReportsHome from "./ReportsHome.svelte";
import TrialBalance from "./TrialBalance.svelte";

const param = (url: URL, name: string) => url.searchParams.get(name) ?? "";

export const qb_reports = new Route(
  "qb_reports",
  ReportsHome,
  async () => {
    // A snapshot of all the data (by month, quarter or year as it fits).
    const all = await get_qb_profit_loss({
      start: "",
      end: "",
      by: "total",
      compare: "",
    });
    const total = all.columns[0];
    const trend = total?.start
      ? await get_qb_profit_loss({
          start: iso(total.start),
          end: iso(total.end),
          by: trend_by(total.start, total.end),
          compare: "",
        })
      : all;
    return { trend };
  },
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
    // Charts cover the same dates: a trend and this vs the previous period.
    const total =
      statement.columns.find((c) => c.label === "Total") ??
      statement.columns[0];
    const first = total?.start ?? today;
    const last = total?.end ?? today;
    const range = { start: iso(first), end: iso(last) };
    // Short periods get the 12 months up to them, for context.
    const trend_start =
      trend_by(first, last) === "month" &&
      (last.getUTCFullYear() - first.getUTCFullYear()) * 12 +
        last.getUTCMonth() -
        first.getUTCMonth() <
        2
        ? new Date(Date.UTC(last.getUTCFullYear(), last.getUTCMonth() - 11, 1))
        : first;
    const [trend, compared] = await Promise.all([
      get_qb_profit_loss({
        start: iso(trend_start),
        end: iso(last),
        by: trend_by(trend_start, last),
        compare: "",
      }),
      get_qb_profit_loss({ ...range, by: "total", compare: "1" }),
    ]);
    return { statement, trend, compared, period, today, by, compare };
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
    const as_of = statement.columns[0]?.end ?? today;
    const history = await get_qb_balance_trend(iso(as_of), 12);
    return { statement, history, today, compare };
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
