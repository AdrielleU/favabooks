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
  boolean,
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

const qb_review = object({
  rows: array(qb_review_row),
  accounts: array(
    object({
      account: string,
      balance: decimal,
      currency: string,
      to_review: number,
    }),
  ),
});

export type QbReviewRow = ValidationT<typeof qb_review_row>;
export type QbReview = ValidationT<typeof qb_review>;
export type QbEditResult = ValidationT<typeof qb_edit_result>;

/** Transactions flagged ! within the header filters, newest first. */
export const get_qb_review = async (params: QbFilters): Promise<QbReview> =>
  qb_get("qb_review", { ...params }, qb_review);

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

const qb_posting_row = object({
  entry_hash: string,
  date,
  flag: string,
  payee: string,
  narration: string,
  amount: decimal,
  currency: string,
  others: array(string),
});

const qb_postings = object({ rows: array(qb_posting_row), total: number });

const qb_register_row = object({
  entry_hash: string,
  date,
  flag: string,
  payee: string,
  narration: string,
  amount: decimal,
  currency: string,
  balance: decimal,
  categories: array(string),
});

const qb_register = object({
  account: string,
  opening: array(object({ currency: string, amount: decimal })),
  rows: array(qb_register_row),
});

const qb_export = object({
  key: string,
  title: string,
  description: string,
  query: string,
});

export type QbPostingRow = ValidationT<typeof qb_posting_row>;
export type QbPostings = ValidationT<typeof qb_postings>;
export type QbRegister = ValidationT<typeof qb_register>;
export type QbRegisterRow = ValidationT<typeof qb_register_row>;
const qb_exports = object({
  year: number,
  years: array(number),
  exports: array(qb_export),
});

export type QbExport = ValidationT<typeof qb_export>;
export type QbExports = ValidationT<typeof qb_exports>;

/** Search for bulk reclassify: postings to exactly one account. */
export const get_qb_postings = async (
  params: QbFilters & {
    account_name: string;
    payee: string;
    min_amount: string;
    max_amount: string;
  },
): Promise<QbPostings> => qb_get("qb_postings", { ...params }, qb_postings);

/** Register for one account; only the time filter applies. */
export const get_qb_register = async (params: {
  account_name: string;
  time: string;
}): Promise<QbRegister> => qb_get("qb_register", params, qb_register);

/** Year-end report queries; `year` "" means the latest year with data. */
export const get_qb_exports = async (params: {
  year: string;
}): Promise<QbExports> => qb_get("qb_exports", params, qb_exports);

const qb_bank_format = object({
  key: string,
  bank: string,
  kind: string,
  download: string,
  columns: array(string),
  amounts: string,
  has_balance: boolean,
  confidence: string,
});

const qb_bank_imports = object({
  formats: array(qb_bank_format),
  importers: array(object({ name: string, key: string, account: string })),
  config_file: string,
  import_dirs: array(string),
  errors: array(string),
});

export type QbBankFormat = ValidationT<typeof qb_bank_format>;
export type QbBankImports = ValidationT<typeof qb_bank_imports>;

/** Supported bank formats and this ledger's import setup. */
export const get_qb_bank_formats = async (): Promise<QbBankImports> =>
  qb_get("qb_bank_formats", {}, qb_bank_imports);
