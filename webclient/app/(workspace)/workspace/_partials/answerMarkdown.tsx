import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Answers can repeat text planted in an indexed document. That text must not
// fetch an outside URL or send a Referer.
const remarkPlugins = [remarkGfm];
const disallowedElements = ["img"];
const components: Components = {
  a: ({ href, children }) => (
    <a href={href} rel="noreferrer">
      {children}
    </a>
  ),
};

export function AnswerMarkdown({ children }: { children: string }) {
  return (
    <Markdown
      remarkPlugins={remarkPlugins}
      skipHtml
      disallowedElements={disallowedElements}
      components={components}
    >
      {children}
    </Markdown>
  );
}
