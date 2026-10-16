import { Route } from "../../reports/route.ts";
import type { QbBankImports } from "../api.ts";
import { get_qb_bank_formats } from "../api.ts";
import Banks from "./Banks.svelte";

export const qb_banks = new Route<{ setup: QbBankImports }>(
  "qb_banks",
  Banks,
  async () => ({ setup: await get_qb_bank_formats() }),
  () => "Bank formats",
);
