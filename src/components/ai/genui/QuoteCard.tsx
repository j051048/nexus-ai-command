import React from 'react';
import { Quote } from 'lucide-react';
import { cn } from '@/lib/utils';

interface QuoteCardProps {
  quote: string;
  author?: string;
  source?: string;
  avatar?: string;
}

export default function QuoteCard({ quote, author, source, avatar }: QuoteCardProps) {
  if (!quote) return null;

  return (
    <div className="p-4">
      <div className="rounded-lg border bg-card p-5 relative">
        {/* Quote icon */}
        <Quote className="w-8 h-8 text-muted-foreground/20 absolute top-4 right-4" />

        {/* Quote text */}
        <blockquote className="text-sm leading-relaxed pr-8">
          <p className="italic text-foreground/90">&ldquo;{quote}&rdquo;</p>
        </blockquote>

        {/* Attribution */}
        {(author || source) && (
          <div className="mt-4 flex items-center gap-3">
            {avatar ? (
              <img
                src={avatar}
                alt={author || ''}
                className="w-8 h-8 rounded-full object-cover border"
              />
            ) : author ? (
              <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold text-muted-foreground">
                {author.charAt(0).toUpperCase()}
              </div>
            ) : null}
            <div className="flex flex-col">
              {author && (
                <span className="text-sm font-medium">{author}</span>
              )}
              {source && (
                <span className="text-xs text-muted-foreground">{source}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
