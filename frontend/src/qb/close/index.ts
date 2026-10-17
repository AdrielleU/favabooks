import { Route } from "../../reports/route.ts";
import { get_qb_close, get_qb_year_checks } from "../api.ts";
import CloseBooks from "./CloseBooks.svelte";

export const qb_close_books = new Route(
  "qb_close_books",
  CloseBooks,
  async (url) => {
    const info = await get_qb_close();
    const picked = url.searchParams.get("date") ?? "";
    const day = picked ? new Date(`${picked}T00:00:00Z`) : info.suggested;
    const year = Number.isNaN(day.getTime())
      ? info.suggested.getUTCFullYear()
      : day.getUTCFullYear();
    return { info, checks: await get_qb_year_checks(year), year };
  },
  () => "Close books",
);
