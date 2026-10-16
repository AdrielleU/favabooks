import { Route } from "../../reports/route.ts";
import { get_url_filters } from "../../stores/filters.ts";
import type { QbPostings } from "../api.ts";
import { get_qb_postings } from "../api.ts";
import Reclassify from "./Reclassify.svelte";
import type { ReclassifySearch } from "./search.ts";

export const qb_reclassify = new Route<{
  search: ReclassifySearch;
  result: QbPostings | null;
}>(
  "qb_reclassify",
  Reclassify,
  async (url) => {
    const param = (key: string) => url.searchParams.get(key) ?? "";
    const search: ReclassifySearch = {
      account_name: param("account_name"),
      payee: param("payee"),
      min_amount: param("min_amount"),
      max_amount: param("max_amount"),
    };
    const { time, account, filter } = get_url_filters(url);
    const result = search.account_name
      ? await get_qb_postings({ ...search, time, account, filter })
      : null;
    return { search, result };
  },
  () => "Bulk reclassify",
);
