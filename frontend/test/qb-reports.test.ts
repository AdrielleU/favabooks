import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import type { QbNode } from "../src/qb/api.ts";
import {
  as_of_choices,
  parents,
  pct_change,
  tree_rows,
} from "../src/qb/reports/helpers.ts";

const leaf = (account: string, n: number): QbNode => ({
  account,
  name: account.split(":").pop() ?? account,
  amounts: [n],
  children: [],
  own: [n],
});

const tree: QbNode = {
  account: "Expenses",
  name: "Expenses",
  amounts: [35],
  own: [5],
  children: [
    leaf("Expenses:Cloud", 10),
    {
      account: "Expenses:Legal",
      name: "Legal",
      amounts: [20],
      own: [0],
      children: [leaf("Expenses:Legal:Startup", 20)],
    },
  ],
};

test("tree rows, expanded and collapsed", () => {
  const rows = tree_rows("Expenses", tree, new Set(), [35]);
  deepEqual(
    rows.map((r) => [r.kind, r.label, r.depth, r.amounts]),
    [
      ["section", "Expenses", 0, []],
      ["account", "Expenses (other)", 1, [5]],
      ["account", "Cloud", 1, [10]],
      ["group", "Legal", 1, []],
      ["account", "Startup", 2, [20]],
      ["total", "Total Legal", 1, [20]],
      ["total", "Total expenses", 0, [35]],
    ],
  );
  const collapsed = tree_rows(
    "Expenses",
    tree,
    new Set(["Expenses:Legal"]),
    [35],
  );
  const legal = collapsed.filter((r) => r.account === "Expenses:Legal");
  deepEqual(
    legal.map((r) => [r.kind, r.collapsed, r.amounts]),
    [["account", true, [20]]],
  );
  deepEqual(
    tree_rows("Income", null, new Set(), [0]).map((r) => r.label),
    ["Income", "Total income"],
  );
});

test("parents, change, as-of choices", () => {
  deepEqual(parents(tree), ["Expenses:Legal"]);
  deepEqual(parents(null), []);
  equal(pct_change(150, 100), 50);
  equal(pct_change(50, -100), 150);
  equal(pct_change(5, 0), null);
  const choices = as_of_choices(new Date("2026-05-10T00:00:00Z"), [2025, 2024]);
  deepEqual(
    choices.map((c) => [c.key, c.date]),
    [
      ["today", "2026-05-10"],
      ["last-month", "2026-04-30"],
      ["last-quarter", "2026-03-31"],
      ["last-year", "2025-12-31"],
      ["end-2024", "2024-12-31"],
    ],
  );
});
