import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import { kind_label, leaf, totals } from "../src/qb/transactions/helpers.ts";

test("leaf", () => {
  equal(leaf("Expenses:Office:Supplies"), "Office:Supplies");
  equal(leaf("Expenses"), "Expenses");
});

test("kind label", () => {
  equal(kind_label("expense"), "Expense");
  equal(kind_label("transfer"), "Transfer");
  equal(kind_label("other"), "Journal");
});

test("totals in cents", () => {
  deepEqual(
    totals([
      { kind: "expense", amount: 0.1 },
      { kind: "expense", amount: 0.2 },
      { kind: "income", amount: 5 },
      { kind: "transfer", amount: 100 },
    ]),
    { expense: 30, income: 500 },
  );
});
