import { equal } from "node:assert/strict";
import { test } from "node:test";

import { label_for } from "../src/qb/nickname-labels.ts";

test("labels", () => {
  const nicknames = { "Liabilities:CreditCard:Card-6800": "Chase Ink" };
  equal(label_for(nicknames, "Liabilities:CreditCard:Card-6800"), "Chase Ink");
  equal(
    label_for(nicknames, "Liabilities:CreditCard:Card-8360"),
    "CreditCard:Card-8360",
  );
  equal(label_for(nicknames, "Assets"), "Assets");
});
