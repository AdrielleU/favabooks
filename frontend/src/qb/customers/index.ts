import { Route } from "../../reports/route.ts";
import type { QbCustomer } from "../api.ts";
import { get_qb_customers } from "../api.ts";
import Customers from "./Customers.svelte";

export const qb_customers = new Route<{ customers: QbCustomer[] }>(
  "qb_customers",
  Customers,
  async () => ({ customers: await get_qb_customers() }),
  () => "Customers",
);
