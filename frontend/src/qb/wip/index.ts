import { Route } from "../../reports/route.ts";
import WipPage from "./WipPage.svelte";

export interface WipPageProps {
  /** Page heading. */
  title: string;
  /** One line on what the page will do. */
  description: string;
}

/** Create a route that renders the shared "(WIP)" page. */
export function wip_route(
  report: string,
  title: string,
  description: string,
): Route<WipPageProps> {
  return new Route<WipPageProps>(
    report,
    WipPage,
    () => ({ title, description }),
    () => `${title} (WIP)`,
  );
}

/** Pages that are planned but not built yet. Every one has a nav entry. */
export const wip_routes = [
  // Phase 2 and 3.
  wip_route(
    "qb_close_books",
    "Close books",
    "Lock a period so entries on or before the date can't be edited.",
  ),
  wip_route(
    "qb_vendors",
    "Vendors",
    "Everyone you have paid, from vendor: metadata, with 1099 totals.",
  ),
  wip_route("qb_bills", "Bills", "Bills to pay, with A/P aging."),
];
