import { Route } from "../../reports/route.ts";
import { get_qb_chart } from "../api.ts";
import ChartOfAccounts from "./ChartOfAccounts.svelte";

export const qb_chart = new Route(
  "qb_chart",
  ChartOfAccounts,
  async () => ({ chart: await get_qb_chart() }),
  () => "Chart of accounts",
);
