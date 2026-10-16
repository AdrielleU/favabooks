/**
 * qb-fork: wording for the two sides of the books, so Invoices/Customers
 * and Bills/Vendors share their pages (no DOM imports).
 */
import type { QbSide } from "../api.ts";

export interface SideText {
  side: QbSide;
  /** "invoice" or "bill". */
  doc: string;
  /** "Invoices" or "Bills". */
  docs_title: string;
  /** "customer" or "vendor". */
  party: string;
  /** "Customer" or "Vendor". */
  party_title: string;
  /** "Customers" or "Vendors". */
  parties_title: string;
  docs_report: string;
  parties_report: string;
  /** What the Invoices or Bills page is for. */
  docs_intro: string;
  /** Where the other party's documents come from. */
  parties_intro: string;
  /** Empty-state text for the documents list. */
  docs_empty: string;
  parties_empty: string;
  /** Exports that can be imported. */
  import_sources: string;
  /** "Income account" or "Expense account". */
  account_label: string;
  /** "Accounts Receivable" or "Accounts Payable". */
  ledger_label: string;
  /** Recording explanation. */
  record_intro: string;
  /** "deposit" or "payment" (the money that settles a document). */
  payment: string;
  /** Matching explanation, after "Pick the ... that paid it." */
  match_intro: string;
  /** Where to import those payments from. */
  match_empty: string;
  /** "Total sales" or "Total spent". */
  total_label: string;
  /** "Paid, last 30 days" bar segment. */
  paid_label: string;
  /** Checkbox on Customers/Vendors. */
  owing_label: string;
  /** "Paid into" or "Paid with". */
  paid_with_label: string;
}

export const SALES: SideText = {
  side: "invoice",
  doc: "invoice",
  docs_title: "Invoices",
  party: "customer",
  party_title: "Customer",
  parties_title: "Customers",
  docs_report: "qb_invoices",
  parties_report: "qb_customers",
  docs_intro:
    "Keep track of invoices you send from Stripe, a PDF or another app. Import or record them here, then match each one to the deposit that paid it.",
  parties_intro:
    "Customers come from your invoices and income: the customer on Stripe sales and recorded invoices, or the payee of a deposit filed as income.",
  docs_empty:
    "Invoices paid through Stripe show up here on their own once you import Stripe payouts (with the invoice_id column). For anything else, import your invoice list as a CSV or record one invoice at a time.",
  parties_empty:
    "Customers appear when you import Stripe payouts, import or record invoices, or file a deposit as income.",
  import_sources:
    "Stripe (Invoices → Export), QuickBooks (Sales → Invoices → Export), FreshBooks, Wave or any spreadsheet with an invoice number, customer, date and total.",
  account_label: "Income account",
  ledger_label: "Accounts Receivable",
  record_intro:
    "For an invoice you already sent from somewhere else. It's booked as money the customer owes you (Accounts Receivable) until you match the payment.",
  payment: "deposit",
  match_intro:
    "Its category becomes Accounts Receivable, so the money isn't counted as income twice.",
  match_empty:
    "Import the bank or Stripe statement with this payment in Import files, then come back.",
  total_label: "Total sales",
  paid_label: "Paid, last 30 days",
  owing_label: "Only customers who owe you",
  paid_with_label: "into",
};

export const PURCHASES: SideText = {
  side: "bill",
  doc: "bill",
  docs_title: "Bills",
  party: "vendor",
  party_title: "Vendor",
  parties_title: "Vendors",
  docs_report: "qb_bills",
  parties_report: "qb_vendors",
  docs_intro:
    "Bills are your vendors' invoices. Expenses imported with the vendor's invoice number show here already paid. Record or import bills you'll pay later, then match the payment from your bank or card.",
  parties_intro:
    "Vendors are everyone you've paid: the vendor on your bills, or the payee of any expense.",
  docs_empty:
    "Expenses that carry the vendor's invoice number (an invoice column in your expense import) show up here as paid bills. Record or import bills you haven't paid yet.",
  parties_empty:
    "Vendors appear when you import or categorize expenses, or record bills.",
  import_sources:
    "QuickBooks (Expenses → Bills → Export), Bill.com, Xero or any spreadsheet with a bill number, vendor, date and total.",
  account_label: "Expense account",
  ledger_label: "Accounts Payable",
  record_intro:
    "For a bill you've received but not paid yet. It's booked as money you owe the vendor (Accounts Payable) until you match the payment.",
  payment: "payment",
  match_intro:
    "Its category becomes Accounts Payable, so the expense isn't counted twice.",
  match_empty:
    "Import the bank or card statement with this payment in Import files, then come back.",
  total_label: "Total spent",
  paid_label: "Paid, last 30 days",
  owing_label: "Only vendors you owe",
  paid_with_label: "with",
};
