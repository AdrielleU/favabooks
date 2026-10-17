import type { FrontendRoute } from "../reports/route.ts";
import { qb_banks } from "./banks/index.ts";
import { qb_chart } from "./chart/index.ts";
import { qb_dashboard } from "./dashboard/index.ts";
import {
  qb_bills,
  qb_customers,
  qb_invoices,
  qb_vendors,
} from "./docs/index.ts";
import { qb_exports } from "./exports/index.ts";
import { qb_reclassify } from "./reclassify/index.ts";
import { qb_reconcile } from "./reconcile/index.ts";
import { qb_register } from "./register/index.ts";
import {
  qb_balance_sheet,
  qb_general_ledger,
  qb_profit_loss,
  qb_reports,
  qb_trial_balance,
} from "./reports/index.ts";
import { qb_review } from "./review/index.ts";
import { qb_transactions } from "./transactions/index.ts";
import { wip_routes } from "./wip/index.ts";

/** All qb-fork routes. Each name must also be in CLIENT_SIDE_REPORTS. */
export const qb_routes: FrontendRoute[] = [
  qb_dashboard,
  qb_review,
  qb_banks,
  qb_transactions,
  qb_register,
  qb_reconcile,
  qb_reclassify,
  qb_reports,
  qb_profit_loss,
  qb_balance_sheet,
  qb_trial_balance,
  qb_general_ledger,
  qb_exports,
  qb_chart,
  qb_customers,
  qb_invoices,
  qb_vendors,
  qb_bills,
  ...wip_routes,
];
