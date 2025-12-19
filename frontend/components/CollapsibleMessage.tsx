"use client";

import { useState, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CollapsibleMessageProps {
  content: string;
  children?: ReactNode;
  previewLength?: number;
  className?: string;
}

const LINE_BREAK_THRESHOLD = 3; // Number of line breaks that trigger collapsible
const MIN_LENGTH = 500; // Minimum character length to trigger collapsible

export default function CollapsibleMessage({ 
  content,
  children,
  previewLength = 300,
  className 
}: CollapsibleMessageProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Check if content should be collapsible
  const lineBreaks = (content.match(/\n/g) || []).length;
  const shouldCollapse = content.length > MIN_LENGTH || lineBreaks > LINE_BREAK_THRESHOLD;
  
  if (!shouldCollapse) {
    return <div className={className}>{children || content}</div>;
  }
  
  const preview = content.substring(0, previewLength);
  const remaining = content.substring(previewLength);
  const hasMore = remaining.length > 0;
  
  return (
    <div className={className}>
      <div className="whitespace-pre-wrap break-words">
        {isExpanded ? (children || content) : (children ? children : preview)}
        {!isExpanded && hasMore && (
          <span className="text-white/50">...</span>
        )}
      </div>
      {hasMore && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={cn(
            "mt-2 text-xs px-3 py-1 rounded-lg transition-all",
            "bg-white/10 hover:bg-white/20 text-white/70 hover:text-white",
            "border border-white/20"
          )}
        >
          {isExpanded ? "Show less" : `Show more (${Math.ceil(remaining.length / 1000)}k more)`}
        </button>
      )}
    </div>
  );
}

