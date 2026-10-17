import { Route } from "../../reports/route.ts";
import { get_qb_events, get_qb_statistics } from "../api.ts";
import Events from "./Events.svelte";
import Statistics from "./Statistics.svelte";

export const qb_events = new Route(
  "qb_events",
  Events,
  async () => ({ data: await get_qb_events() }),
  () => "Business details & dates",
);

export const qb_statistics = new Route(
  "qb_statistics",
  Statistics,
  async () => ({ data: await get_qb_statistics() }),
  () => "Statistics",
);
