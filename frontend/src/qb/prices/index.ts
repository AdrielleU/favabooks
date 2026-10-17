import { Route } from "../../reports/route.ts";
import { get_qb_prices } from "../api.ts";
import Prices from "./Prices.svelte";

export const qb_prices = new Route(
  "qb_prices",
  Prices,
  async () => ({ data: await get_qb_prices() }),
  () => "Currencies & prices",
);
