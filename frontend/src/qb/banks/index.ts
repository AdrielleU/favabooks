import { Route } from "../../reports/route.ts";
import type { QbImportSetup } from "../api.ts";
import { get_qb_import_setup } from "../api.ts";
import Banks from "./Banks.svelte";

export const qb_banks = new Route<{ setup: QbImportSetup }>(
  "qb_banks",
  Banks,
  async () => ({ setup: await get_qb_import_setup() }),
  () => "Bank & card accounts",
);
