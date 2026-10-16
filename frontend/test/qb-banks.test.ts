import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import {
  account_component,
  guess_role,
  guess_roles,
  layout_from_roles,
  roles_problem,
  suggest_account,
} from "../src/qb/banks/helpers.ts";

test("qb banks: suggested account names", () => {
  equal(account_component("Bank of America"), "BankOfAmerica");
  equal(account_component("U.S. Bank"), "USBank");
  equal(account_component("1st Bank"), "Bank1stBank");
  equal(
    suggest_account("Chase", "Credit card", "1234"),
    "Liabilities:CreditCard:Chase-1234",
  );
  equal(
    suggest_account("Mercury", "Business banking", ""),
    "Assets:Bank:Mercury",
  );
  equal(suggest_account("Stripe", "Payouts", "9999"), "Assets:Stripe");
});

test("qb banks: column roles guessed from headers", () => {
  equal(guess_role("Posting Date"), "date");
  equal(guess_role("Running Balance"), "balance");
  equal(guess_role("Withdrawals"), "debit");
  equal(guess_role("Deposits"), "credit");
  equal(guess_role("Transaction Amount"), "amount");
  equal(guess_role("Payee"), "description");
  equal(guess_role("Check #"), "ignore");
  // Each role is guessed once; later look-alikes are ignored.
  deepEqual(guess_roles(["Date", "Post Date", "Description", "Amount"]), [
    "date",
    "ignore",
    "description",
    "amount",
  ]);
});

test("qb banks: roles guessed from sample values", () => {
  deepEqual(
    guess_roles(
      ["When", "What", "Out", "In", "Ref"],
      [
        ["02/03/2026", "Coffee Shop", "4.50", "", "A1"],
        ["02/04/2026", "Client payment", "", "250.00", "A2"],
      ],
    ),
    ["date", "description", "debit", "credit", "ignore"],
  );
  // Number-only columns are not taken as the description.
  deepEqual(guess_roles(["A", "B"], [["12.00", "2026-01-02"]]), [
    "ignore",
    "date",
  ]);
});

test("qb banks: roles must be complete before saving", () => {
  equal(roles_problem(["description", "amount"]), "Choose a Date column.");
  equal(roles_problem(["date", "amount"]), "Choose a Description column.");
  equal(
    roles_problem(["date", "description", "debit"]),
    "Choose an Amount column, or both Money out and Money in.",
  );
  equal(
    roles_problem(["date", "date", "description"]),
    "Two columns are set to Date.",
  );
  equal(roles_problem(["date", "description", "debit", "credit"]), "");
});

test("qb banks: layout from roles", () => {
  const header = ["When", "What", "Out", "In", "Amount"];
  deepEqual(
    layout_from_roles(
      header,
      ["date", "description", "debit", "credit", "ignore"],
      true,
      "",
    ),
    {
      date: "When",
      description: "What",
      amount: "",
      debit: "Out",
      credit: "In",
      negate: false,
      date_format: "",
      balance: "",
    },
  );
  const one = layout_from_roles(
    header,
    ["date", "description", "debit", "credit", "amount"],
    true,
    "%m/%d/%Y",
  );
  deepEqual(
    [one.amount, one.debit, one.negate, one.date_format],
    ["Amount", "", true, "%m/%d/%Y"],
  );
});
