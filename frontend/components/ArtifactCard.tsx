"use client";

import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/apiConfig";

interface ArtifactCardProps {
  path: string;
  type?: "file" | "email" | "url";
  size?: string;
  onReveal?: () => void;
  onCopy?: () => void;
}

// Helper to determine file type from extension
function getFileType(path: string): "image" | "pdf" | "other" {
  const ext = path.toLowerCase().split('.').pop() || '';
  if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'].includes(ext)) {
    return 'image';
  }
  if (ext === 'pdf') {
    return 'pdf';
  }
  return 'other';
}

export default function ArtifactCard({ 
  path, 
  type = "file", 
  size,
  onReveal,
  onCopy 
}: ArtifactCardProps) {
  const [copied, setCopied] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const fileType = type === "file" ? getFileType(path) : "other";
  
  // Generate preview URL for images and PDFs
  useEffect(() => {
    if (fileType === "image") {
      // For images, use the file path directly (assuming it's accessible)
      // In production, you'd want to serve this through your API
      setPreviewUrl(path);
    } else if (fileType === "pdf") {
      // For PDFs, we can show a thumbnail via a PDF viewer service or API
      // For now, we'll just show an icon
      setPreviewUrl(null);
    } else {
      setPreviewUrl(null);
    }
  }, [path, fileType]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onCopy?.();
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleReveal = async () => {
    // For macOS, use the reveal command via a backend API
    if (type === "file") {
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
        // Fallback: just copy the path
        handleCopy();
      }
    }
    onReveal?.();
  };

  const getIcon = () => {
    switch (type) {
      case "email":
        return "✉️";
      case "url":
        return "🔗";
      default:
        return "📄";
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ 
        opacity: 1, 
        scale: 1, 
        y: 0,
        boxShadow: [
          "0 0 0px rgba(9, 255, 255, 0)",
          "0 4px 12px rgba(9, 255, 255, 0.2)",
          "0 2px 8px rgba(9, 255, 255, 0.1)",
        ]
      }}
      transition={{ 
        duration: 0.3,
        ease: "easeOut"
      }}
      className="mt-3 rounded-card bg-surface border border-surface-outline p-3 hover:border-surface-outline-strong transition-colors duration-200"
    >
      <div className="flex items-start justify-between gap-3">
        {/* Preview thumbnail for images - 60x60 */}
        {previewUrl && fileType === "image" && (
          <div className="relative flex-shrink-0 w-[60px] h-[60px] rounded-lg overflow-hidden border border-white/20 bg-white/5 group">
            <img
              src={previewUrl}
              alt={path.split("/").pop() || "Preview"}
              className="w-full h-full object-cover"
              onError={() => setPreviewUrl(null)}
            />
            {/* Download icon overlay */}
            <button
              onClick={handleReveal}
              className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
              title="Download/Reveal"
            >
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
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
            </button>
          </div>
        )}
        
        {/* PDF icon thumbnail - 60x60 */}
        {fileType === "pdf" && (
          <div className="relative flex-shrink-0 w-[60px] h-[60px] rounded-lg border border-white/20 bg-red-500/20 flex items-center justify-center group">
            <span className="text-2xl">📄</span>
            {/* Download icon overlay */}
            <button
              onClick={handleReveal}
              className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-lg"
              title="Download/Reveal"
            >
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
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
            </button>
          </div>
        )}
        
        {/* Keynote/other file thumbnail - 60x60 */}
        {!previewUrl && fileType !== "pdf" && type === "file" && (
          <div className="relative flex-shrink-0 w-[60px] h-[60px] rounded-lg border border-white/20 bg-white/5 flex items-center justify-center group">
            <span className="text-xl">{getIcon()}</span>
            {/* Download icon overlay */}
            <button
              onClick={handleReveal}
              className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-lg"
              title="Download/Reveal"
            >
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
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
            </button>
          </div>
        )}
        
        <div className="flex items-start gap-2 flex-1 min-w-0">
          {/* Only show icon if no thumbnail was rendered */}
          {!previewUrl && fileType !== "pdf" && type !== "file" && (
            <span className="text-lg flex-shrink-0">{getIcon()}</span>
          )}
          <div className="flex-1 min-w-0">
            <div className="text-sm text-foreground font-semibold truncate" title={path}>
              {path.split("/").pop() || path}
            </div>
            {path.includes("/") && (
              <div className="text-xs text-foreground-muted truncate mt-0.5" title={path}>
                {path}
              </div>
            )}
            {size && (
              <div className="text-xs text-foreground-subtle mt-1 font-medium">{size}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {type === "file" && (
            <button
              onClick={handleReveal}
              className={cn(
                "px-3 py-1.5 text-xs rounded-lg transition-all duration-200 font-medium",
                "bg-surface border border-surface-outline hover:border-surface-outline-strong",
                "text-foreground-muted hover:text-foreground"
              )}
              title="Reveal in Finder"
            >
              Reveal
            </button>
          )}
          <button
            onClick={handleCopy}
            className={cn(
              "px-3 py-1.5 text-xs rounded-lg transition-all duration-200 font-medium",
              copied
                ? "bg-success-bg text-success border border-success-border"
                : "bg-surface border border-surface-outline hover:border-surface-outline-strong text-foreground-muted hover:text-foreground"
            )}
            title="Copy path"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

