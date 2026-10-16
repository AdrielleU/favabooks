/**
 * Typed calls to the qb_* endpoints in src/fava/qb_api.py.
 *
 * Mirrors the private api_url/fetch helpers in ../api/index.ts so that
 * upstream file stays untouched.
 */
import { get as store_get } from "svelte/store";

import { fetch_json } from "../lib/fetch.ts";
import type {
  ValidationError,
  ValidationT,
  Validator,
} from "../lib/validation.ts";
import {
  array,
  date,
  decimal,
  number,
  object,
  string,
} from "../lib/validation.ts";
import { base_url } from "../stores/index.ts";
import { set_mtime } from "../stores/mtime.ts";

class QbInvalidResponseError extends Error {
  constructor(cause: ValidationError) {
    super("Invalid data returned by a qb_* endpoint.", { cause });
  }
}

async function qb_get<R>(
  endpoint: `qb_${string}`,
  params: Record<string, string>,
  validator: Validator<R>,
): Promise<R> {
  const url = new URL(
    `${store_get(base_url)}api/${endpoint}`,
    window.location.href,
  );
  for (const [key, value] of Object.entries(params)) {
    if (value !== "") {
      url.searchParams.set(key, value);
    }
  }
  const json = await fetch_json(url);
  if (typeof json.mtime === "string") {
    set_mtime(json.mtime);
  }
  return validator(json.data).unwrap(QbInvalidResponseError);
}

async function qb_put<R>(
  endpoint: `qb_${string}`,
  body: Record<string, unknown>,
  validator: Validator<R>,
): Promise<R> {
  const url = new URL(
    `${store_get(base_url)}api/${endpoint}`,
    window.location.href,
  );
  const json = await fetch_json(url, {
    method: "PUT",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
  // Record our own save so Fava doesn't announce it as an external change.
  if (typeof json.mtime === "string") {
    set_mtime(json.mtime);
  }
  return validator(json.data).unwrap(QbInvalidResponseError);
}

const qb_amount = object({ account: string, amount: decimal });

const qb_profit_loss = object({
  month: string,
  income: decimal,
  expenses: decimal,
  net: decimal,
});

const qb_dashboard = object({
  currency: string,
  balances_date: date,
  balances: array(qb_amount),
  this_month: qb_profit_loss,
  last_month: qb_profit_loss,
  top_expenses: array(qb_amount),
  review_count: number,
  error_count: number,
});

export type QbAmount = ValidationT<typeof qb_amount>;
export type QbProfitLoss = ValidationT<typeof qb_profit_loss>;
export type QbDashboard = ValidationT<typeof qb_dashboard>;

/** Dashboard data for the month of the time filter (or today). */
export const get_qb_dashboard = async (params: {
  time: string;
}): Promise<QbDashboard> => qb_get("qb_dashboard", params, qb_dashboard);

/** Header filters that the qb endpoints respect. */
export interface QbFilters {
  time: string;
  account: string;
  filter: string;
}

const qb_review_row = object({
  entry_hash: string,
  date,
  payee: string,
  narration: string,
  account: string,
  amount: decimal,
  currency: string,
  categories: array(string),
});

const qb_edit_result = object({
  changed: number,
  failed: array(object({ entry_hash: string, error: string })),
});

export type QbReviewRow = ValidationT<typeof qb_review_row>;
export type QbEditResult = ValidationT<typeof qb_edit_result>;

/** Transactions flagged ! within the header filters, newest first. */
export const get_qb_review = async (
  params: QbFilters,
): Promise<QbReviewRow[]> =>
  qb_get("qb_review", { ...params }, array(qb_review_row));

/** Accept entries (! to *), optionally moving from_account to to_account. */
export const put_qb_accept = async (body: {
  entry_hashes: string[];
  from_account?: string;
  to_account?: string;
}): Promise<QbEditResult> => qb_put("qb_accept", body, qb_edit_result);

/** Move postings from one account to another across many entries. */
export const put_qb_reclassify = async (body: {
  entry_hashes: string[];
  from_account: string;
  to_account: string;
}): Promise<QbEditResult> => qb_put("qb_reclassify", body, qb_edit_result);
