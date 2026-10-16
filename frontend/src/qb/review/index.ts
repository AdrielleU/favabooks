import { Route } from "../../reports/route.ts";
import { get_url_filters } from "../../stores/filters.ts";
import type { QbReviewRow } from "../api.ts";
import { get_qb_review } from "../api.ts";
import Review from "./Review.svelte";

export const qb_review = new Route<{ rows: QbReviewRow[] }>(
  "qb_review",
  Review,
  async (url) => {
    const { time, account, filter } = get_url_filters(url);
    return { rows: await get_qb_review({ time, account, filter }) };
  },
  () => "For review",
);
