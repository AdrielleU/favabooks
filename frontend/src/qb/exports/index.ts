import { Route } from "../../reports/route.ts";
import type { QbCheck, QbExports } from "../api.ts";
import { get_qb_exports, get_qb_year_checks } from "../api.ts";
import Exports from "./Exports.svelte";

export const qb_exports = new Route<{ data: QbExports; checks: QbCheck[] }>(
  "qb_exports",
  Exports,
  async (url) => {
    const data = await get_qb_exports({
      year: url.searchParams.get("year") ?? "",
    });
    return { data, checks: await get_qb_year_checks(data.year) };
  },
  ({ data }) => `Export for CPA: ${data.year.toString()}`,
);
