import { Route } from "../../reports/route.ts";
import { get_url_filters } from "../../stores/filters.ts";
import type { QbRegister } from "../api.ts";
import { get_qb_register } from "../api.ts";
import Register from "./Register.svelte";

export const qb_register = new Route<{
  account_name: string;
  register: QbRegister | null;
}>(
  "qb_register",
  Register,
  async (url) => {
    const account_name = url.searchParams.get("account_name") ?? "";
    const { time } = get_url_filters(url);
    const register = account_name
      ? await get_qb_register({ account_name, time })
      : null;
    return { account_name, register };
  },
  ({ account_name }) =>
    account_name ? `Register: ${account_name}` : "Register",
);
