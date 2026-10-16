import { Route } from "../../reports/route.ts";
import { get_qb_docs, get_qb_parties } from "../api.ts";
import Docs from "./Docs.svelte";
import Parties from "./Parties.svelte";
import { resolve_period } from "./periods.ts";
import { PURCHASES, SALES, type SideText } from "./sides.ts";

/** The date filter in the URL. */
function url_period(url: URL) {
  const param = (name: string) => url.searchParams.get(name) ?? "";
  const today = new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00Z`);
  return {
    today,
    period: resolve_period(
      param("period") || "all",
      param("from"),
      param("to"),
      today,
    ),
  };
}

function docs_route(text: SideText) {
  return new Route(
    text.docs_report,
    Docs,
    async (url) => ({
      text,
      data: await get_qb_docs(text.side),
      tab: url.searchParams.get("status") ?? "",
      party: url.searchParams.get("party") ?? "",
      ...url_period(url),
    }),
    () => text.docs_title,
  );
}

function parties_route(text: SideText) {
  return new Route(
    text.parties_report,
    Parties,
    async (url) => {
      const { today, period } = url_period(url);
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
