import { Route } from "../../reports/route.ts";
import type { QbExports } from "../api.ts";
import { get_qb_exports } from "../api.ts";
import Exports from "./Exports.svelte";

export const qb_exports = new Route<{ data: QbExports }>(
  "qb_exports",
  Exports,
  async (url) => ({
    data: await get_qb_exports({ year: url.searchParams.get("year") ?? "" }),
  }),
  ({ data }) => `Export reports ${data.year.toString()}`,
);
