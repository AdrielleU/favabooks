import { Route } from "../../reports/route.ts";
import type { QbExport } from "../api.ts";
import { get_qb_exports } from "../api.ts";
import Exports from "./Exports.svelte";

export const qb_exports = new Route<{ year: number; exports: QbExport[] }>(
  "qb_exports",
  Exports,
  async (url) => {
    const param = Number.parseInt(url.searchParams.get("year") ?? "", 10);
    const year = Number.isNaN(param) ? new Date().getFullYear() : param;
    return { year, exports: await get_qb_exports({ year: year.toString() }) };
  },
  ({ year }) => `Export reports ${year.toString()}`,
);
