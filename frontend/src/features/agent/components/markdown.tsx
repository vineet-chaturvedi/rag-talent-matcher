import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { linkEmployeeCodes } from "../transcript";

/**
 * The agent's answer, rendered from Markdown (lists, bold, tables: GitHub style).
 *
 * Safe by design: react-markdown builds React elements and ignores raw HTML in the text, so even if a
 * resume contained "<script>" and the model repeated it, nothing would run. Links to our own pages
 * (the EMP-1003 codes) become client-side Links; other links open in a new tab without access to
 * this page ("noopener").
 */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="space-y-3 text-sm leading-relaxed [&_li]:my-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("/") ? (
              <Link href={href as never} className="font-medium text-primary hover:underline">
                {children}
              </Link>
            ) : (
              <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                {children}
              </a>
            ),
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs [&_td]:border-t [&_td]:px-2 [&_td]:py-1.5 [&_th]:px-2 [&_th]:py-1.5 [&_th]:font-medium">
                {children}
              </table>
            </div>
          ),
          code: ({ children }) => <code className="rounded bg-muted px-1 py-0.5 text-xs">{children}</code>,
        }}
      >
        {linkEmployeeCodes(text)}
      </ReactMarkdown>
    </div>
  );
}
