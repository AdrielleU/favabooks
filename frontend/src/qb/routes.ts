import type { FrontendRoute } from "../reports/route.ts";
import { qb_dashboard } from "./dashboard/index.ts";
import { wip_routes } from "./wip/index.ts";

/** All qb-fork routes. Each name must also be in CLIENT_SIDE_REPORTS. */
export const qb_routes: FrontendRoute[] = [qb_dashboard, ...wip_routes];
