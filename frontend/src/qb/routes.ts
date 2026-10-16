import type { FrontendRoute } from "../reports/route.ts";
import { qb_banks } from "./banks/index.ts";
import { qb_dashboard } from "./dashboard/index.ts";
import { qb_exports } from "./exports/index.ts";
import { qb_reclassify } from "./reclassify/index.ts";
import { qb_reconcile } from "./reconcile/index.ts";
import { qb_register } from "./register/index.ts";
import { qb_review } from "./review/index.ts";
import { wip_routes } from "./wip/index.ts";

/** All qb-fork routes. Each name must also be in CLIENT_SIDE_REPORTS. */
export const qb_routes: FrontendRoute[] = [
  qb_dashboard,
  qb_review,
  qb_banks,
  qb_register,
  qb_reconcile,
  qb_reclassify,
  qb_exports,
  ...wip_routes,
];
