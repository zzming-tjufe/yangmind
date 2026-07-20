import ReactMarkdown from "react-markdown";

type Props = {
  content: string;
  className?: string;
};

/** 公告正文：轻量 Markdown 渲染 */
export function MarkdownBody({ content, className }: Props) {
  const text = content.trim() || "（无正文）";
  return (
    <div className={`md-body${className ? ` ${className}` : ""}`}>
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
