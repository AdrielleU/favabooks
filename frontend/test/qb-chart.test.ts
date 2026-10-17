import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import {
  component,
  new_account_name,
  path_parts,
  type_rank,
} from "../src/qb/chart/helpers.ts";

test("type order", () => {
  equal(type_rank("Bank"), 0);
  equal(type_rank("Expenses") > type_rank("Income"), true);
  equal(type_rank("Something else"), 13);
});

test("new account names", () => {
  equal(
    new_account_name("Assets", "Bank", "", "Chase checking"),
    "Assets:Bank:ChaseChecking",
  );
  equal(
    new_account_name("Expenses", "", "", "office supplies"),
    "Expenses:OfficeSupplies",
  );
  equal(
    new_account_name("Expenses", "", "Expenses:Legal", "Filing fees"),
    "Expenses:Legal:FilingFees",
  );
  equal(new_account_name("Assets", "Bank", "", ""), "Assets:Bank");
  equal(new_account_name("Income", "", "", "2026 grants"), "Income:2026Grants");
  equal(new_account_name("Assets", "", "", "-x"), "Assets:X-x");
  deepEqual(path_parts("Expenses:Legal:Startup"), ["Legal", "Startup"]);
});

test("component", () => {
  equal(component("Bank of America  checking!"), "BankOfAmericaChecking");
  equal(component("card-8360"), "Card-8360");
  equal(component(""), "");
});
