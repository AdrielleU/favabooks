import { strict as assert } from "node:assert";
import { test } from "node:test";

import {
  cents,
  cents_string,
  difference,
  parse_amount,
  statement_sign,
} from "../src/qb/reconcile/helpers.ts";

test("cents and back", () => {
  assert.equal(cents(0.1 + 0.2), 30);
  assert.equal(cents(-12.345), -1234);
  assert.equal(cents_string(-1250), "-12.50");
  assert.equal(cents_string(105500), "1055.00");
});

test("statement sign", () => {
  assert.equal(statement_sign("Assets:Bank:Checking"), 1);
  assert.equal(statement_sign("Liabilities:CreditCard:Visa"), -1);
});

test("parse statement amounts", () => {
  assert.equal(parse_amount("$1,234.56"), 123456);
  assert.equal(parse_amount(" 5 "), 500);
  assert.equal(parse_amount("-5.1"), -510);
  assert.equal(parse_amount("(12.00)"), -1200);
  assert.equal(parse_amount(".5"), 50);
  assert.equal(parse_amount(""), null);
  assert.equal(parse_amount("lots"), null);
  assert.equal(parse_amount("1.234"), null);
});

test("difference", () => {
  assert.equal(difference(105500, 0, [100000, 5000, 500]), 0);
  assert.equal(difference(105500, 0, [100000]), 5500);
  assert.equal(difference(-900, 0, []), -900);
});
