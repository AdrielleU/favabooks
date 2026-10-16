import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import { move_target } from "../src/qb/import/move_target.ts";
import type { ProcessedImportableFile } from "../src/reports/import/index.ts";

const files = [
  {
    name: "/books/inbox/chase.csv",
    basename: "chase.csv",
    identified_by_importers: true,
    importers: [
      {
        account: "Assets:Bank:Checking",
        importer_name: "chase_checking:Assets:Bank:Checking",
        new_name: "2026-10-16 chase.csv",
      },
    ],
  },
  {
    name: "/books/inbox/odd.csv",
    basename: "odd.csv",
    identified_by_importers: true,
    importers: [{ account: "", importer_name: "odd", new_name: "x.csv" }],
  },
] as unknown as ProcessedImportableFile[];

const key = "/books/inbox/chase.csv:chase_checking:Assets:Bank:Checking";

test("qb auto-move: the importer's suggestion", () => {
  deepEqual(
    move_target(
      files,
      "/books/inbox/chase.csv",
      "chase_checking:Assets:Bank:Checking",
      new Map(),
      new Map(),
    ),
    { account: "Assets:Bank:Checking", new_name: "2026-10-16 chase.csv" },
  );
});

test("qb auto-move: what was typed in the file list wins", () => {
  deepEqual(
    move_target(
      files,
      "/books/inbox/chase.csv",
      "chase_checking:Assets:Bank:Checking",
      new Map([[key, "Assets:Bank:Savings"]]),
      new Map([[key, "statement.csv"]]),
    ),
    { account: "Assets:Bank:Savings", new_name: "statement.csv" },
  );
});

test("qb auto-move: nothing to move to", () => {
  // Unknown file, unknown importer, or no account suggested.
  equal(
    move_target(files, "/books/inbox/nope.csv", "x", new Map(), new Map()),
    null,
  );
  equal(
    move_target(files, "/books/inbox/chase.csv", "other", new Map(), new Map()),
    null,
  );
  equal(
    move_target(files, "/books/inbox/odd.csv", "odd", new Map(), new Map()),
    null,
  );
});
