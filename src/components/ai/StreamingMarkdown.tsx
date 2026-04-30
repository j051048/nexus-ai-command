import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';

interface StreamingMarkdownProps {
  content: string;
  isStreaming: boolean;
  components: Record<string, React.ComponentType<any>>;
  className?: string;
}

/**
 * Optimized markdown renderer for streaming content.
 * Splits content into a "stable" prefix (memoized, full markdown) and a
 * "tail" (lightweight render, updates frequently). This avoids re-parsing
 * the entire document on every token flush.
 */
export const StreamingMarkdown = React.memo(function StreamingMarkdown({
  content,
  isStreaming,
  components,
  className,
}: StreamingMarkdownProps) {
  // When not streaming, render everything normally
  if (!isStreaming) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    );
  }

  // During streaming: split at the last double-newline (paragraph boundary)
  // The stable prefix gets memoized; only the tail re-renders frequently
  const splitIndex = content.lastIndexOf('\n\n');
  const stableContent = splitIndex > 0 ? content.slice(0, splitIndex) : '';
  const tailContent = splitIndex > 0 ? content.slice(splitIndex) : content;

  return (
    <>
      {stableContent && (
        <MemoizedMarkdown content={stableContent} components={components} />
      )}
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={components}
      >
        {tailContent}
      </ReactMarkdown>
    </>
  );
});

/**
 * Inner component that only re-renders when its content string changes.
 * Since the stable prefix only grows at paragraph boundaries, this
 * dramatically reduces ReactMarkdown re-parse frequency.
 */
const MemoizedMarkdown = React.memo(
  function MemoizedMarkdown({
    content,
    components,
  }: {
    content: string;
    components: Record<string, React.ComponentType<any>>;
  }) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    );
  },
  (prev, next) => prev.content === next.content
);
