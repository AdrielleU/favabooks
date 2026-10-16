import { Route } from "../../reports/route.ts";
import type { QbInvoices } from "../api.ts";
import { get_qb_invoices } from "../api.ts";
import Invoices from "./Invoices.svelte";

export interface InvoicesProps {
  data: QbInvoices;
  /** Status tab ("", unpaid, overdue, paid). */
  tab: string;
  /** Only this customer's invoices ("" for all). */
  customer: string;
}

export const qb_invoices = new Route<InvoicesProps>(
  "qb_invoices",
  Invoices,
  async (url) => ({
    data: await get_qb_invoices(),
    tab: url.searchParams.get("status") ?? "",
    customer: url.searchParams.get("customer") ?? "",
  }),
  () => "Invoices",
);
