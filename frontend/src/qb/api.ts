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
  optional,
  record,
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

async function qb_delete<R>(
  endpoint: `qb_${string}`,
  params: Record<string, string>,
  validator: Validator<R>,
): Promise<R> {
  const url = new URL(
    `${store_get(base_url)}api/${endpoint}`,
    window.location.href,
  );
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  const json = await fetch_json(url, { method: "DELETE" });
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
  from_paid?: string;
  to_paid?: string;
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

// --- Bank & card accounts (connections) -------------------------------------

const qb_layout = object({
  date: string,
  description: string,
  amount: string,
  debit: string,
  credit: string,
  negate: boolean,
  date_format: string,
  balance: string,
});

const qb_connection = object({
  id: string,
  kind: string,
  account: string,
  name: string,
  format: string,
  layout: optional(qb_layout),
  filename: string,
  skip_stripe: boolean,
  payout_account: string,
  currency: string,
});

const qb_import_setup = object({
  status: string,
  config_file: string,
  import_dirs: array(string),
  errors: array(string),
  connections: array(
    object({
      connection: qb_connection,
      bank: string,
      kind_label: string,
      download: string,
      last_date: optional(date),
      documents: number,
    }),
  ),
  banks: array(
    object({
      bank: string,
      formats: array(
        object({
          key: string,
          kind: string,
          download: string,
          confidence: string,
        }),
      ),
    }),
  ),
  inbox: array(
    object({
      filename: string,
      basename: string,
      importers: array(string),
      detected: array(string),
      header: array(string),
      sample: array(array(string)),
    }),
  ),
});

const qb_preview = object({
  matches: boolean,
  rows: array(
    object({ date, payee: string, amount: decimal, currency: string }),
  ),
  total: number,
  parsed: number,
  problem: string,
});

export type QbLayout = ValidationT<typeof qb_layout>;
export type QbConnection = ValidationT<typeof qb_connection>;
export type QbImportSetup = ValidationT<typeof qb_import_setup>;
export type QbPreview = ValidationT<typeof qb_preview>;

/** Saved connections, supported banks and inbox files. */
export const get_qb_import_setup = async (): Promise<QbImportSetup> =>
  qb_get("qb_import_setup", {}, qb_import_setup);

/** Save a connection (new when `id` is ""); returns its id. */
export const put_qb_connection = async (
  connection: Partial<QbConnection>,
): Promise<string> => qb_put("qb_connection", { connection }, string);

/** Remove a connection. */
export const delete_qb_connection = async (id: string): Promise<string> =>
  qb_delete("qb_connection", { connection_id: id }, string);

/** Turn on Bank connections for this ledger. */
export const put_qb_import_enable = async (): Promise<string> =>
  qb_put("qb_import_enable", {}, string);

/** What a draft connection makes of a file in the inbox. */
export const put_qb_connection_preview = async (
  filename: string,
  connection: Partial<QbConnection>,
): Promise<QbPreview> =>
  qb_put("qb_connection_preview", { filename, connection }, qb_preview);

// --- Account overview and Reconcile -----------------------------------------

const qb_account_overview = object({
  account: string,
  balance: decimal,
  currency: string,
  transactions: number,
  last_date: optional(date),
});

const qb_reconcile = object({
  account: string,
  currency: string,
  beginning_balance: decimal,
  rows: array(
    object({
      entry_hash: string,
      date,
      payee: string,
      narration: string,
      amount: decimal,
    }),
  ),
  books_balance: decimal,
  history: array(object({ date, comment: string })),
});

export type QbAccountOverview = ValidationT<typeof qb_account_overview>;
export type QbReconcile = ValidationT<typeof qb_reconcile>;

/** Bank and card accounts with balance and activity. */
export const get_qb_accounts_overview = async (): Promise<
  QbAccountOverview[]
> => qb_get("qb_accounts_overview", {}, array(qb_account_overview));

/** Reconciliation state for an account up to a statement date. */
export const get_qb_reconcile = async (params: {
  account_name: string;
  end_date: string;
}): Promise<QbReconcile> => qb_get("qb_reconcile", params, qb_reconcile);

/** Finish a reconciliation (the difference must be zero). */
export const put_qb_reconcile = async (body: {
  account_name: string;
  end_date: string;
  ending_balance: string;
  entry_hashes: string[];
}): Promise<{ reconciled: number; balance_assertion: boolean }> =>
  qb_put(
    "qb_reconcile",
    body,
    object({ reconciled: number, balance_assertion: boolean }),
  );

// --- All transactions and categories ----------------------------------------

const qb_transactions = object({
  rows: array(
    object({
      entry_hash: string,
      date,
      flag: string,
      kind: string,
      payee: string,
      narration: string,
      categories: array(string),
      paid_with: array(string),
      amount: decimal,
      currency: string,
      receipts: array(object({ name: string, filename: string })),
      tags: array(string),
    }),
  ),
  total: number,
  counts: record(number),
});

const qb_category = object({
  account: string,
  count: number,
  total: decimal,
  currency: string,
});

export type QbTransactions = ValidationT<typeof qb_transactions>;
export type QbTransactionRow = QbTransactions["rows"][number];
export type QbCategory = ValidationT<typeof qb_category>;

/** Transactions in the header filters, newest first. */
export const get_qb_transactions = async (
  params: QbFilters & { search: string; kind: string },
): Promise<QbTransactions> =>
  qb_get("qb_transactions", { ...params }, qb_transactions);

/** Income and expense accounts used in the header filters. */
export const get_qb_categories = async (
  params: QbFilters,
): Promise<QbCategory[]> =>
  qb_get("qb_categories", { ...params }, array(qb_category));

// --- Sales: customers and invoices ------------------------------------------

const qb_receipt = object({ name: string, filename: string });

const qb_invoice = object({
  number: string,
  customer: string,
  date,
  due: optional(date),
  amount: decimal,
  paid: decimal,
  balance: decimal,
  currency: string,
  status: string,
  source: string,
  memo: string,
  entry_hashes: array(string),
  receipts: array(qb_receipt),
});

const qb_invoices = object({
  ar_account: string,
  today: date,
  invoices: array(qb_invoice),
  income_accounts: array(string),
});

const qb_customer = object({
  name: string,
  email: string,
  invoices: number,
  sales: decimal,
  open_balance: decimal,
  overdue: decimal,
  currency: string,
  last_date: date,
});

const qb_deposit = object({
  entry_hash: string,
  date,
  payee: string,
  narration: string,
  account: string,
  amount: decimal,
  currency: string,
  category: string,
  exact: boolean,
});

const qb_invoice_row = object({
  line: number,
  number: string,
  customer: string,
  date: optional(date),
  due: optional(date),
  amount: optional(decimal),
  paid: decimal,
  status: string,
  state: string,
  problem: string,
  email: string,
  currency: string,
  paid_date: optional(date),
});

const qb_invoice_preview = object({
  header: array(string),
  mapping: record(string),
  rows: array(qb_invoice_row),
});

export type QbInvoice = ValidationT<typeof qb_invoice>;
export type QbInvoices = ValidationT<typeof qb_invoices>;
export type QbCustomer = ValidationT<typeof qb_customer>;
export type QbDeposit = ValidationT<typeof qb_deposit>;
export type QbInvoicePreview = ValidationT<typeof qb_invoice_preview>;

/** Every invoice in the ledger. */
export const get_qb_invoices = async (): Promise<QbInvoices> =>
  qb_get("qb_invoices", {}, qb_invoices);

/** Customers from invoices and income. */
export const get_qb_customers = async (): Promise<QbCustomer[]> =>
  qb_get("qb_customers", {}, array(qb_customer));

/** Fields of an invoice to record. */
export interface QbInvoiceForm {
  customer: string;
  number: string;
  date: string;
  due: string;
  amount: string;
  income_account: string;
  memo: string;
  email: string;
}

/** Book one invoice; returns its entry hash (to attach the PDF to). */
export const put_qb_invoice = async (
  invoice: QbInvoiceForm,
): Promise<{ entry_hash: string }> =>
  qb_put("qb_invoice", { invoice }, object({ entry_hash: string }));

/** Deposits that could have paid an invoice, best match first. */
export const get_qb_invoice_deposits = async (
  number: string,
): Promise<QbDeposit[]> =>
  qb_get("qb_invoice_deposits", { number }, array(qb_deposit));

/** Mark a deposit as the payment for an invoice. */
export const put_qb_invoice_payment = async (
  number: string,
  entry_hash: string,
): Promise<string> =>
  qb_put("qb_invoice_payment", { number, entry_hash }, string);

/** Read a CSV of invoices; `mapping` overrides the guessed columns. */
export const put_qb_invoice_csv_preview = async (
  content: string,
  mapping: Record<string, string> | null,
): Promise<QbInvoicePreview> =>
  qb_put("qb_invoice_csv_preview", { content, mapping }, qb_invoice_preview);

/** Book the new rows of a CSV of invoices. */
export const put_qb_invoice_csv_import = async (body: {
  content: string;
  mapping: Record<string, string>;
  income_account: string;
  payment_account: string;
}): Promise<{ invoices: number; payments: number }> =>
  qb_put(
    "qb_invoice_csv_import",
    body,
    object({ invoices: number, payments: number }),
  );
