"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/apiConfig";
import DocumentPreviewModal from "./DocumentPreviewModal";

interface FileHit {
  name: string;
  path: string;
  score: number;
  display_path?: string;
  meta?: {
    file_type?: string;
    total_pages?: number;
  };
  thumbnail_url?: string;
  preview_url?: string;
  result_type?: "document" | "image";
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

// Helper to determine if file is previewable
function isPreviewable(file: FileHit): boolean {
  if (!file.meta?.file_type) return false;
  const ext = file.meta.file_type.toLowerCase();
  return ["pdf", "html", "png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext);
}

// Helper to get preview file type
function getPreviewFileType(file: FileHit): "pdf" | "html" | "image" {
  if (!file.meta?.file_type) return "pdf";
  const ext = file.meta.file_type.toLowerCase();
  if (ext === "pdf") return "pdf";
  if (ext === "html") return "html";
  if (["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext)) return "image";
  return "pdf";
}

export default function FileList({ files, summaryBlurb, totalCount }: FileListProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [previewFile, setPreviewFile] = useState<FileHit | null>(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
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

  const handlePreview = (file: FileHit) => {
    setPreviewFile(file);
    setShowPreviewModal(true);
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
                {/* Image thumbnail or file type icon */}
                {file.thumbnail_url || (file.result_type === "image" && file.meta?.file_type && ["jpg", "jpeg", "png", "gif", "svg", "webp"].includes(file.meta.file_type.toLowerCase())) ? (
                  <div 
                    className={cn(
                      "relative flex-shrink-0 w-[60px] h-[60px] rounded-lg overflow-hidden border border-surface-outline bg-surface group",
                      isPreviewable(file) && "cursor-pointer hover:border-accent-primary/50 transition-colors"
                    )}
                    onClick={() => isPreviewable(file) && handlePreview(file)}
                    title={isPreviewable(file) ? "Click to preview" : ""}
                  >
                    <img
                      src={file.thumbnail_url ? `${apiBaseUrl}${file.thumbnail_url}` : `${apiBaseUrl}/api/files/thumbnail?path=${encodeURIComponent(file.path)}&max_size=256`}
                      alt={file.name}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        // Fallback to icon if thumbnail fails to load
                        const target = e.target as HTMLImageElement;
                        target.style.display = "none";
                        const parent = target.parentElement;
                        if (parent) {
                          parent.innerHTML = `<div class="flex items-center justify-center w-full h-full text-xl">${getFileTypeIcon(file.meta?.file_type)}</div>`;
                        }
                      }}
                    />
                    {/* Hover overlay to indicate clickability */}
                    {isPreviewable(file) && (
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                        <svg
                          className="w-5 h-5 text-white"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                          />
                        </svg>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex-shrink-0 text-xl">
                    {getFileTypeIcon(file.meta?.file_type)}
                  </div>
                )}

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
                    {file.display_path || file.path}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {isPreviewable(file) && (
                  <button
                    onClick={() => handlePreview(file)}
                    className={cn(
                      "px-2 py-1 text-xs rounded-lg transition-all duration-200 font-medium",
                      "bg-accent-primary/10 hover:bg-accent-primary/20 border border-accent-primary/20",
                      "text-accent-primary"
                    )}
                    title="Preview"
                  >
                    Preview
                  </button>
                )}
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

      {/* Preview Modal */}
      {previewFile && (
        <DocumentPreviewModal
          isOpen={showPreviewModal}
          onClose={() => {
            setShowPreviewModal(false);
            setPreviewFile(null);
          }}
          filePath={previewFile.path}
          fileType={getPreviewFileType(previewFile)}
        />
      )}
    </div>
  );
}

