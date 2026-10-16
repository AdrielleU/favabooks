import { Route } from "../../reports/route.ts";
import { get_url_filters } from "../../stores/filters.ts";
import type { QbDashboard } from "../api.ts";
import { get_qb_dashboard } from "../api.ts";
import Dashboard from "./Dashboard.svelte";

export const qb_dashboard = new Route<{ data: QbDashboard }>(
  "qb_dashboard",
  Dashboard,
  async (url) => ({
    data: await get_qb_dashboard({ time: get_url_filters(url).time }),
  }),
  () => "Dashboard",
);
