"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/apiConfig";

interface DocumentEntry {
  name: string;
  path: string;
  size: number;
  modified: string; // ISO date string
  preview: string;
  size_human: string;
  type?: string;
  total_pages?: number;
}

interface DocumentListProps {
  documents: DocumentEntry[];
  summaryMessage?: string;
  totalCount?: number;
  hasMore?: boolean;
}

// Helper to get file type icon
function getFileTypeIcon(fileType?: string): string {
  if (!fileType) return "📄";
  const ext = fileType.toLowerCase();
  if (ext === "pdf") return "📄";
  if (["doc", "docx"].includes(ext)) return "📝";
  if (["xls", "xlsx"].includes(ext)) return "📊";
  if (["ppt", "pptx"].includes(ext)) return "📽️";
  if (["jpg", "jpeg", "png", "gif", "svg"].includes(ext)) return "🖼️";
  if (["mp3", "wav", "flac"].includes(ext)) return "🎵";
  if (["mp4", "mov", "avi"].includes(ext)) return "🎬";
  if (ext === "zip") return "📦";
  return "📄";
}

// Helper to format date
function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateString;
  }
}

export default function DocumentList({ documents, summaryMessage, totalCount, hasMore }: DocumentListProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const DISPLAY_LIMIT = 20; // Show more than FileList since these are directory listings
  const displayDocuments = documents.slice(0, DISPLAY_LIMIT);
  const hiddenCount = documents.length > DISPLAY_LIMIT ? documents.length - DISPLAY_LIMIT : 0;

  const handleCopy = async (path: string, index: number) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleReveal = async (path: string) => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/reveal-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      if (!response.ok) {
        throw new Error("Failed to reveal file");
      }
    } catch (err) {
      console.error("Failed to reveal file:", err);
      // Fallback: copy the path
      await navigator.clipboard.writeText(path);
    }
  };

  if (documents.length === 0) {
    return (
      <div className="mt-3 rounded-card bg-surface border border-surface-outline p-4 text-center">
        <p className="text-text-muted text-sm">No documents found</p>
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-3">
      {/* Summary message */}
      {summaryMessage && (
        <div className="text-sm text-text-primary leading-relaxed mb-2">
          {summaryMessage}
        </div>
      )}

      {/* Document grid */}
      <div className="grid grid-cols-1 gap-2">
        {displayDocuments.map((doc, index) => (
          <motion.div
            key={`${doc.path}-${index}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.02 }} // Faster animation for directory listings
            className={cn(
              "rounded-card bg-surface border border-surface-outline p-3",
              "hover:border-surface-outline-strong transition-colors duration-200"
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                {/* File type icon */}
                <div className="flex-shrink-0 text-xl">
                  {getFileTypeIcon(doc.type)}
                </div>

                {/* Document info */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-text-primary font-semibold truncate" title={doc.name}>
                    {doc.name}
                  </div>

                  {/* Preview snippet */}
                  {doc.preview && (
                    <div className="text-xs text-text-muted mt-1 line-clamp-2" title={doc.preview}>
                      {doc.preview}
                    </div>
                  )}

                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-text-subtle">
                      {doc.size_human}
                    </span>
                    {doc.type && (
                      <span className="text-xs text-text-subtle">
                        • {doc.type.toUpperCase()}
                      </span>
                    )}
                    {doc.total_pages && doc.total_pages > 0 && (
                      <span className="text-xs text-text-subtle">
                        • {doc.total_pages} page{doc.total_pages !== 1 ? "s" : ""}
                      </span>
                    )}
                    <span className="text-xs text-text-subtle">
                      • Modified {formatDate(doc.modified)}
                    </span>
                  </div>

                  <div className="text-xs text-text-subtle truncate mt-0.5" title={doc.path}>
                    {doc.path}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => handleReveal(doc.path)}
                  className={cn(
                    "px-2 py-1 text-xs rounded-lg transition-all duration-200 font-medium",
                    "bg-surface border border-surface-outline hover:border-surface-outline-strong",
                    "text-text-muted hover:text-text-primary"
                  )}
                  title="Reveal in Finder"
                >
                  Reveal
                </button>
                <button
                  onClick={() => handleCopy(doc.path, index)}
                  className={cn(
                    "px-2 py-1 text-xs rounded-lg transition-all duration-200 font-medium",
                    copiedIndex === index
                      ? "bg-success-bg text-success border border-success-border"
                      : "bg-surface border border-surface-outline hover:border-surface-outline-strong text-text-muted hover:text-text-primary"
                  )}
                  title="Copy path"
                >
                  {copiedIndex === index ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Hidden count indicator and load more hint */}
      <div className="flex items-center justify-between text-xs text-text-muted pt-2">
        {hiddenCount > 0 && (
          <span>
            +{hiddenCount} more document{hiddenCount !== 1 ? "s" : ""} hidden
            {totalCount && totalCount > documents.length && ` (${totalCount} total found)`}
          </span>
        )}
        {hasMore && (
          <span className="text-text-subtle">
            Use pagination or filters to see more results
          </span>
        )}
      </div>
    </div>
  );
}
