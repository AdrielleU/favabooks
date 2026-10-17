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
  lazy,
  number,
  object,
  optional,
  record,
  string,
  tuple,
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
  months: array(date),
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
  params: QbFilters & {
    search: string;
    kind: string;
    start: string;
    end: string;
  },
): Promise<QbTransactions> =>
  qb_get("qb_transactions", { ...params }, qb_transactions);

/** Income and expense accounts used in the header filters. */
export const get_qb_categories = async (
  params: QbFilters,
): Promise<QbCategory[]> =>
  qb_get("qb_categories", { ...params }, array(qb_category));

// --- Invoices and bills, customers and vendors -----------------------------

/** Which side of the books: sales (invoices) or purchases (bills). */
export type QbSide = "invoice" | "bill";

const qb_receipt = object({ name: string, filename: string });

const qb_doc = object({
  key: string,
  number: string,
  party: string,
  date,
  due: optional(date),
  amount: decimal,
  paid: decimal,
  balance: decimal,
  currency: string,
  status: string,
  direct: boolean,
  paid_with: array(string),
  categories: array(string),
  memo: string,
  entry_hashes: array(string),
  receipts: array(qb_receipt),
  paid_date: optional(date),
});

const qb_docs = object({
  ledger_account: string,
  today: date,
  docs: array(qb_doc),
  accounts: array(string),
});

const qb_party = object({
  name: string,
  email: string,
  docs: number,
  total: decimal,
  open_balance: decimal,
  overdue: decimal,
  currency: string,
  last_date: date,
  category: string,
  bank_paid: decimal,
});

const qb_payment = object({
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

const qb_doc_row = object({
  line: number,
  number: string,
  party: string,
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

const qb_doc_preview = object({
  header: array(string),
  mapping: record(string),
  rows: array(qb_doc_row),
});

export type QbDoc = ValidationT<typeof qb_doc>;
export type QbDocs = ValidationT<typeof qb_docs>;
export type QbParty = ValidationT<typeof qb_party>;
export type QbPayment = ValidationT<typeof qb_payment>;
export type QbDocPreview = ValidationT<typeof qb_doc_preview>;

/** Every invoice or bill in the ledger. */
export const get_qb_docs = async (side: QbSide): Promise<QbDocs> =>
  qb_get(side === "invoice" ? "qb_invoices" : "qb_bills", {}, qb_docs);

/** Customers or vendors, with totals for the start..end period. */
export const get_qb_parties = async (
  side: QbSide,
  start: string,
  end: string,
): Promise<QbParty[]> =>
  qb_get(
    side === "invoice" ? "qb_customers" : "qb_vendors",
    { start, end },
    array(qb_party),
  );

/** Fields of an invoice or bill to record. */
export interface QbDocForm {
  party: string;
  number: string;
  date: string;
  due: string;
  amount: string;
  account: string;
  memo: string;
  email: string;
}

/** Book one invoice or bill; returns its entry hash (to attach the PDF). */
export const put_qb_doc = async (
  side: QbSide,
  doc: QbDocForm,
): Promise<{ entry_hash: string }> =>
  qb_put(`qb_${side}`, { doc }, object({ entry_hash: string }));

/** Payments that could settle an invoice or bill, best match first. */
export const get_qb_doc_payments = async (
  side: QbSide,
  key: string,
): Promise<QbPayment[]> =>
  qb_get(`qb_${side}_payments`, { key }, array(qb_payment));

/** Mark a transaction as the payment for an invoice or bill. */
export const put_qb_doc_payment = async (
  side: QbSide,
  key: string,
  entry_hash: string,
): Promise<string> => qb_put(`qb_${side}_payment`, { key, entry_hash }, string);

/** Read a CSV of invoices or bills; `mapping` overrides the guess. */
export const put_qb_doc_csv_preview = async (
  side: QbSide,
  content: string,
  mapping: Record<string, string> | null,
): Promise<QbDocPreview> =>
  qb_put(`qb_${side}_csv_preview`, { content, mapping }, qb_doc_preview);

/** Book the new rows of a CSV of invoices or bills. */
export const put_qb_doc_csv_import = async (
  side: QbSide,
  body: {
    content: string;
    mapping: Record<string, string>;
    account: string;
    payment_account: string;
  },
): Promise<{ docs: number; payments: number }> =>
  qb_put(
    `qb_${side}_csv_import`,
    body,
    object({ docs: number, payments: number }),
  );

// --- Reports ----------------------------------------------------------------

/** An account in a report tree; `amounts` include its children. */
export interface QbNode {
  account: string;
  name: string;
  amounts: number[];
  children: QbNode[];
  own: number[];
}

const qb_node: Validator<QbNode> = object({
  account: string,
  name: string,
  amounts: array(decimal),
  children: array(lazy(() => qb_node)),
  own: array(decimal),
});

const qb_column = object({
  label: string,
  start: optional(date),
  end: date,
});

const qb_statement = object({
  title: string,
  company: string,
  currency: string,
  columns: array(qb_column),
  blocks: array(
    object({
      kind: string,
      key: string,
      title: string,
      amounts: array(decimal),
      node: optional(qb_node),
    }),
  ),
  unconverted: array(string),
});

const qb_trial_balance = object({
  company: string,
  currency: string,
  as_of: date,
  fiscal_start: date,
  rows: array(object({ account: string, debit: decimal, credit: decimal })),
  debit: decimal,
  credit: decimal,
  unconverted: array(string),
});

const qb_general_ledger = object({
  company: string,
  currency: string,
  start: date,
  end: date,
  accounts: array(
    object({
      account: string,
      opening: decimal,
      rows: array(
        object({
          entry_hash: string,
          date,
          payee: string,
          narration: string,
          split: array(string),
          amount: decimal,
          balance: decimal,
        }),
      ),
      closing: decimal,
    }),
  ),
  unconverted: array(string),
});

const qb_check = object({
  key: string,
  title: string,
  ok: boolean,
  detail: string,
  report: string,
  params: record(string),
});

export type QbStatement = ValidationT<typeof qb_statement>;
export type QbColumn = ValidationT<typeof qb_column>;
export type QbTrialBalance = ValidationT<typeof qb_trial_balance>;
export type QbGeneralLedger = ValidationT<typeof qb_general_ledger>;
export type QbCheck = ValidationT<typeof qb_check>;

/** Profit and loss; `by` is total, month, quarter or year. */
export const get_qb_profit_loss = async (params: {
  start: string;
  end: string;
  by: string;
  compare: string;
}): Promise<QbStatement> => qb_get("qb_profit_loss", params, qb_statement);

/** Balance sheet at the end of `as_of`. */
export const get_qb_balance_sheet = async (params: {
  as_of: string;
  compare: string;
}): Promise<QbStatement> => qb_get("qb_balance_sheet", params, qb_statement);

/** Trial balance at the end of `as_of`. */
export const get_qb_trial_balance = async (
  as_of: string,
): Promise<QbTrialBalance> =>
  qb_get("qb_trial_balance", { as_of }, qb_trial_balance);

/** General ledger for a period, optionally one account subtree. */
export const get_qb_general_ledger = async (params: {
  start: string;
  end: string;
  account: string;
}): Promise<QbGeneralLedger> =>
  qb_get("qb_general_ledger", params, qb_general_ledger);

/** Year-end checks before sending the books to an accountant. */
export const get_qb_year_checks = async (year: number): Promise<QbCheck[]> =>
  qb_get("qb_year_checks", { year: year.toString() }, array(qb_check));

// --- QuickBooks Online export -------------------------------------------------

const qb_qbo_export = object({
  year: number,
  mode: string,
  currency: string,
  accounts: array(
    object({
      name: string,
      type: string,
      detail_type: string,
      account: string,
    }),
  ),
  customers: array(object({ name: string, email: string })),
  vendors: array(object({ name: string, email: string })),
  lines: array(
    object({
      journal_no: string,
      date,
      account: string,
      debit: decimal,
      credit: decimal,
      description: string,
      name: string,
    }),
  ),
  journals: number,
  skipped: array(string),
});

export type QbQboExport = ValidationT<typeof qb_qbo_export>;

/** QuickBooks Online import files for a year. */
export const get_qb_qbo_export = async (
  year: number,
  mode: "transactions" | "balances",
): Promise<QbQboExport> =>
  qb_get("qb_qbo_export", { year: year.toString(), mode }, qb_qbo_export);

const qb_balance_point = object({
  date,
  assets: decimal,
  liabilities: decimal,
  equity: decimal,
});

export type QbBalancePoint = ValidationT<typeof qb_balance_point>;

/** Assets, liabilities and equity at month ends up to `as_of`. */
export const get_qb_balance_trend = async (
  as_of: string,
  months: number,
): Promise<QbBalancePoint[]> =>
  qb_get(
    "qb_balance_trend",
    { as_of, months: months.toString() },
    array(qb_balance_point),
  );

// --- Chart of accounts --------------------------------------------------------

const qb_chart = object({
  currency: string,
  accounts: array(
    object({
      account: string,
      type: string,
      detail_type: string,
      balance: decimal,
      transactions: number,
      open_date: optional(date),
      close_date: optional(date),
      last_date: optional(date),
      nickname: string,
    }),
  ),
  roots: record(string),
  year_start: date,
});

export type QbChart = ValidationT<typeof qb_chart>;
export type QbChartAccount = QbChart["accounts"][number];

/** Every account with its type, balance and activity. */
export const get_qb_chart = async (): Promise<QbChart> =>
  qb_get("qb_chart", {}, qb_chart);

/** Add an account. */
export const put_qb_account_open = async (body: {
  account: string;
  date: string;
  currency: string;
}): Promise<string> => qb_put("qb_account_open", body, string);

/** Close an account. */
export const put_qb_account_close = async (body: {
  account: string;
  date: string;
}): Promise<string> => qb_put("qb_account_close", body, string);

/** Account nicknames (from `nickname:` on Open directives). */
export const get_qb_nicknames = async (): Promise<Record<string, string>> =>
  qb_get("qb_nicknames", {}, record(string));

/** Set (or with "" remove) an account's nickname. */
export const put_qb_account_nickname = async (body: {
  account: string;
  nickname: string;
}): Promise<string> => qb_put("qb_account_nickname", body, string);

// --- Currencies and prices ----------------------------------------------------

const qb_price = object({
  entry_hash: string,
  date,
  currency: string,
  price: decimal,
  quote: string,
});

const qb_prices = object({
  home: string,
  currencies: array(
    object({
      currency: string,
      name: string,
      postings: number,
      last_used: optional(date),
      latest: optional(qb_price),
      previous: optional(qb_price),
      needs_price: boolean,
    }),
  ),
  prices: array(qb_price),
});

export type QbPrices = ValidationT<typeof qb_prices>;
export type QbPrice = ValidationT<typeof qb_price>;

/** Currencies used and every price. */
export const get_qb_prices = async (): Promise<QbPrices> =>
  qb_get("qb_prices", {}, qb_prices);

/** Add a price. */
export const put_qb_price = async (body: {
  date: string;
  currency: string;
  price: string;
  quote: string;
}): Promise<string> => qb_put("qb_price", body, string);

/** Delete a price. */
export const delete_qb_price = async (entry_hash: string): Promise<string> =>
  qb_delete("qb_price", { entry_hash }, string);

// --- Events and statistics ------------------------------------------------------

const qb_event = object({
  entry_hash: string,
  date,
  type: string,
  description: string,
});

const qb_events = object({
  today: date,
  types: array(
    object({
      type: string,
      current: optional(qb_event),
      upcoming: optional(qb_event),
      count: number,
    }),
  ),
  events: array(qb_event),
  suggestions: array(string),
});

const qb_statistics = object({
  today: date,
  first_date: optional(date),
  last_date: optional(date),
  transactions: number,
  to_review: number,
  open_accounts: number,
  documents: number,
  errors: number,
  entries: record(number),
  months: array(
    object({ month: date, transactions: number, to_review: number }),
  ),
  accounts: array(
    object({
      account: string,
      postings: number,
      last_date: optional(date),
      days: optional(number),
    }),
  ),
  postings: array(tuple(string, number)),
});

export type QbEvents = ValidationT<typeof qb_events>;
export type QbStatistics = ValidationT<typeof qb_statistics>;

/** Events with the current value per type. */
export const get_qb_events = async (): Promise<QbEvents> =>
  qb_get("qb_events", {}, qb_events);

/** Add an event. */
export const put_qb_event = async (body: {
  date: string;
  type: string;
  description: string;
}): Promise<string> => qb_put("qb_event", body, string);

/** Delete an event. */
export const delete_qb_event = async (entry_hash: string): Promise<string> =>
  qb_delete("qb_event", { entry_hash }, string);

/** Entry counts, monthly activity and account freshness. */
export const get_qb_statistics = async (): Promise<QbStatistics> =>
  qb_get("qb_statistics", {}, qb_statistics);

// --- Close books ----------------------------------------------------------------

const qb_close_state = object({
  closed_through: optional(date),
  history: array(
    object({ entry_hash: string, date, note: string, checks: number }),
  ),
  suggested: date,
  today: date,
});

export type QbCloseState = ValidationT<typeof qb_close_state>;

/** Whether and how far the books are closed. */
export const get_qb_close = async (): Promise<QbCloseState> =>
  qb_get("qb_close", {}, qb_close_state);

/** Close the books through a date. */
export const put_qb_close = async (body: {
  date: string;
  note: string;
}): Promise<string> => qb_put("qb_close", body, string);

/** Reopen the books (remove the latest close). */
export const delete_qb_close = async (): Promise<string> =>
  qb_delete("qb_close", {}, string);
