import assert from "node:assert/strict";
import { test } from "node:test";

import { findExcerpt } from "./citation-match";

const text = "Refund rules\nCustomers receive refunds\n  within 14 days. Gift cards are final.";

function matched(source: string, excerpt: string | null | undefined) {
  const match = findExcerpt(source, excerpt);
  return match && source.slice(match.start, match.end);
}

test("finds an exact match", () => {
  assert.equal(matched(text, "Gift cards are final."), "Gift cards are final");
});

test("matches across different line breaks, spacing and case", () => {
  assert.equal(
    matched(text, "customers RECEIVE refunds within\t14 days."),
    "Customers receive refunds\n  within 14 days",
  );
});

test("ignores markdown syntax in the excerpt", () => {
  assert.equal(matched("Revenue increased.", "**Revenue** increased."), "Revenue increased");
});

test("returns null when nothing matches", () => {
  assert.equal(findExcerpt(text, "Refunds take 30 days."), null);
});

test("returns null for an empty or missing excerpt", () => {
  assert.equal(findExcerpt(text, ""), null);
  assert.equal(findExcerpt(text, "  \n"), null);
  assert.equal(findExcerpt(text, null), null);
});
