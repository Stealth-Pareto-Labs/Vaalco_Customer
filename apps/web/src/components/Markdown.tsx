"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Markdown — renders LLM output (bold, tables, lists, code) as real HTML,
 * styled for the dark theme. Used by the chat answers. GitHub-flavoured
 * markdown (remark-gfm) gives us proper tables.
 */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="md text-[15px] leading-relaxed text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-ink">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          h1: ({ children }) => <h3 className="mb-2 mt-1 text-[16px] font-semibold">{children}</h3>,
          h2: ({ children }) => <h3 className="mb-2 mt-1 text-[15.5px] font-semibold">{children}</h3>,
          h3: ({ children }) => <h4 className="mb-1.5 mt-1 text-[15px] font-semibold">{children}</h4>,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer" className="text-primary underline underline-offset-2">
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="mono rounded bg-surface2 px-1.5 py-0.5 text-[13px] text-ink">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="mono mb-2 overflow-x-auto rounded-lg border border-line bg-surface2 p-3 text-[13px] last:mb-0">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-l-2 border-line2 pl-3 text-mut last:mb-0">{children}</blockquote>
          ),
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-[13.5px]">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead>{children}</thead>,
          th: ({ children }) => (
            <th className="border border-line bg-surface2 px-3 py-1.5 text-left font-semibold text-ink">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="tnum border border-line px-3 py-1.5 align-top text-ink">{children}</td>
          ),
          hr: () => <hr className="my-3 border-line" />
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
