"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/apiConfig";

interface FileHit {
  name: string;
  path: string;
  score: number;
  meta?: {
    file_type?: string;
    total_pages?: number;
  };
}

interface FileListProps {
  files: FileHit[];
  summaryBlurb?: string;
  totalCount?: number;
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

export default function FileList({ files, summaryBlurb, totalCount }: FileListProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const DISPLAY_LIMIT = 8;
  const displayFiles = files.slice(0, DISPLAY_LIMIT);
  const hiddenCount = files.length > DISPLAY_LIMIT ? files.length - DISPLAY_LIMIT : 0;

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

  if (files.length === 0) {
    return (
      <div className="mt-3 rounded-card bg-surface border border-surface-outline p-4 text-center">
        <p className="text-text-muted text-sm">Nothing matched your request</p>
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-3">
      {/* Summary banner */}
      {summaryBlurb && (
        <div className="text-sm text-text-primary leading-relaxed mb-2">
          {summaryBlurb}
        </div>
      )}

      {/* File grid */}
      <div className="grid grid-cols-1 gap-2">
        {displayFiles.map((file, index) => (
          <motion.div
            key={`${file.path}-${index}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            className={cn(
              "rounded-card bg-surface border border-surface-outline p-3",
              "hover:border-surface-outline-strong transition-colors duration-200"
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                {/* File type icon */}
                <div className="flex-shrink-0 text-xl">
                  {getFileTypeIcon(file.meta?.file_type)}
                </div>

                {/* File info */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-text-primary font-semibold truncate" title={file.name}>
                    {file.name}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-text-muted">
                      Similarity: {(file.score * 100).toFixed(0)}%
                    </span>
                    {file.meta?.file_type && (
                      <span className="text-xs text-text-subtle">
                        • {file.meta.file_type.toUpperCase()}
                      </span>
                    )}
                    {file.meta?.total_pages && (
                      <span className="text-xs text-text-subtle">
                        • {file.meta.total_pages} page{file.meta.total_pages !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-text-subtle truncate mt-0.5" title={file.path}>
                    {file.path}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => handleReveal(file.path)}
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
                  onClick={() => handleCopy(file.path, index)}
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

      {/* Hidden count indicator */}
      {hiddenCount > 0 && (
        <div className="text-xs text-text-muted text-center pt-2">
          +{hiddenCount} more file{hiddenCount !== 1 ? "s" : ""} hidden
          {totalCount && totalCount > files.length && ` (${totalCount} total found)`}
        </div>
      )}
    </div>
  );
}

