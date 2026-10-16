import { router } from "../../router.ts";

/** Search fields, kept in the page URL so reloads and links keep them. */
export interface ReclassifySearch {
  account_name: string;
  payee: string;
  min_amount: string;
  max_amount: string;
}

const FIELDS = ["account_name", "payee", "min_amount", "max_amount"] as const;

/**
 * Navigate to the current page with the given search fields set.
 * Returns the search as it will read back from the URL (trimmed).
 */
export function navigate_with(search: ReclassifySearch): ReclassifySearch {
  const url = new URL(window.location.href);
  const trimmed = { ...search };
  for (const key of FIELDS) {
    const value = search[key].trim();
    trimmed[key] = value;
    if (value) {
      url.searchParams.set(key, value);
    } else {
      url.searchParams.delete(key);
    }
  }
  router.navigate(url);
  return trimmed;
}
