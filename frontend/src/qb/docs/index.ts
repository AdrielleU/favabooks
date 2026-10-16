import { Route } from "../../reports/route.ts";
import { get_qb_docs, get_qb_parties } from "../api.ts";
import Docs from "./Docs.svelte";
import Parties from "./Parties.svelte";
import { period_from_url } from "./periods.ts";
import { PURCHASES, SALES, type SideText } from "./sides.ts";

function docs_route(text: SideText) {
  return new Route(
    text.docs_report,
    Docs,
    async (url) => ({
      text,
      data: await get_qb_docs(text.side),
      tab: url.searchParams.get("status") ?? "",
      party: url.searchParams.get("party") ?? "",
      ...period_from_url(url),
    }),
    () => text.docs_title,
  );
}

function parties_route(text: SideText) {
  return new Route(
    text.parties_report,
    Parties,
    async (url) => {
      const { today, period } = period_from_url(url);
      const [parties, docs] = await Promise.all([
        get_qb_parties(text.side, period.start, period.end),
        get_qb_docs(text.side),
      ]);
      return {
        text,
        parties,
        today,
        period,
        dates: [
          ...docs.docs.map((d) => d.date),
          ...parties.map((p) => p.last_date),
        ],
      };
    },
    () => text.parties_title,
  );
}

export const qb_invoices = docs_route(SALES);
export const qb_bills = docs_route(PURCHASES);
export const qb_customers = parties_route(SALES);
export const qb_vendors = parties_route(PURCHASES);
