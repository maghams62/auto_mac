"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useToast } from "@/lib/useToast";
import { triggerConfetti } from "@/lib/useConfetti";
import { getApiBaseUrl } from "@/lib/apiConfig";

interface CompletionEvent {
  action_type: string;
  summary: string;
  status: string;
  artifact_metadata?: {
    recipients?: string[];
    file_type?: string;
    file_size?: number;
    subject?: string;
    [key: string]: any;
  };
  artifacts?: string[];
}

interface TaskCompletionCardProps {
  completionEvent: CompletionEvent;
  onPreview?: (artifact: string) => void;
  onReveal?: (artifact: string) => void;
}

// Map action types to emojis and colors
function getActionDisplay(actionType: string): { emoji: string; color: string; label: string } {
  const mapping: Record<string, { emoji: string; color: string; label: string }> = {
    email_sent: { emoji: "📧", color: "blue", label: "Email Sent" },
    report_created: { emoji: "📊", color: "purple", label: "Report Created" },
    presentation_created: { emoji: "📽️", color: "cyan", label: "Presentation Created" },
    file_saved: { emoji: "💾", color: "green", label: "File Saved" },
    message_sent: { emoji: "💬", color: "indigo", label: "Message Sent" },
  };

  return mapping[actionType] || { emoji: "✅", color: "green", label: "Task Complete" };
}

// Format file size
function formatFileSize(bytes?: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function TaskCompletionCard({
  completionEvent,
  onPreview,
  onReveal,
}: TaskCompletionCardProps) {
  const { addToast } = useToast();
  const [hasTriggeredConfetti, setHasTriggeredConfetti] = useState(false);
  const apiBaseUrl = getApiBaseUrl();
  const display = getActionDisplay(completionEvent.action_type);

  // Trigger confetti on mount for success status
  useEffect(() => {
    if (completionEvent.status === "success" && !hasTriggeredConfetti) {
      triggerConfetti();
      setHasTriggeredConfetti(true);
      // Show toast with celebratory message
      addToast(completionEvent.summary, "success", 4000);
    }
  }, [completionEvent.status, completionEvent.summary, hasTriggeredConfetti, addToast]);

  const handlePreview = (artifact: string) => {
    if (onPreview) {
      onPreview(artifact);
    } else {
      // Default: open preview URL
      const previewUrl = `${apiBaseUrl}/api/files/preview?path=${encodeURIComponent(artifact)}`;
      window.open(previewUrl, "_blank");
    }
  };

  const handleReveal = async (artifact: string) => {
    if (onReveal) {
      onReveal(artifact);
    } else {
      // Default: call reveal API
      try {
        const response = await fetch(`${apiBaseUrl}/api/reveal-file`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: artifact }),
        });
        if (!response.ok) {
          throw new Error("Failed to reveal file");
        }
      } catch (err) {
        console.error("Failed to reveal file:", err);
      }
    }
  };

  const getFileType = (path: string): string => {
    const ext = path.split(".").pop()?.toLowerCase() || "";
    const types: Record<string, string> = {
      pdf: "PDF",
      key: "Keynote",
      pages: "Pages",
      html: "HTML",
      png: "Image",
      jpg: "Image",
      jpeg: "Image",
    };
    return types[ext] || "File";
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={cn(
        "mt-3 rounded-lg border p-4",
        "bg-gradient-to-br from-surface/50 to-surface/30",
        "backdrop-blur-glass shadow-elevated",
        completionEvent.status === "success"
          ? "border-success-border/50"
          : completionEvent.status === "partial_success"
          ? "border-warning-border/50"
          : "border-glass/50"
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.1, type: "spring", bounce: 0.4 }}
          className={cn(
            "text-3xl flex-shrink-0",
            completionEvent.status === "success" && "animate-bounce"
          )}
        >
          {display.emoji}
        </motion.div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-text-primary mb-1">
            {display.label}
          </h3>
          <p className="text-sm text-text-primary leading-relaxed">
            {completionEvent.summary}
          </p>
        </div>
      </div>

      {/* Metadata */}
      {completionEvent.artifact_metadata && (
        <div className="mt-3 space-y-2 text-xs text-text-muted">
          {completionEvent.artifact_metadata.recipients && (
            <div className="flex items-center gap-2">
              <span className="font-medium">To:</span>
              <span>{completionEvent.artifact_metadata.recipients.join(", ")}</span>
            </div>
          )}
          {completionEvent.artifact_metadata.subject && (
            <div className="flex items-center gap-2">
              <span className="font-medium">Subject:</span>
              <span>{completionEvent.artifact_metadata.subject}</span>
            </div>
          )}
          {completionEvent.artifact_metadata.file_type && (
            <div className="flex items-center gap-2">
              <span className="font-medium">Type:</span>
              <span>{completionEvent.artifact_metadata.file_type}</span>
            </div>
          )}
          {completionEvent.artifact_metadata.file_size && (
            <div className="flex items-center gap-2">
              <span className="font-medium">Size:</span>
              <span>{formatFileSize(completionEvent.artifact_metadata.file_size)}</span>
            </div>
          )}
        </div>
      )}

      {/* Artifacts */}
      {completionEvent.artifacts && completionEvent.artifacts.length > 0 && (
        <div className="mt-3 pt-3 border-t border-glass/30">
          <div className="flex flex-wrap gap-2">
            {completionEvent.artifacts.map((artifact, idx) => {
              const fileName = artifact.split("/").pop() || artifact;
              const fileType = getFileType(artifact);
              const isPreviewable = artifact.match(/\.(pdf|html|png|jpg|jpeg)$/i);
              const isKeynote = artifact.match(/\.(key|pages)$/i);

              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + idx * 0.05 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface/50 border border-surface-outline hover:border-surface-outline-strong transition-colors"
                >
                  <span className="text-xs text-text-muted">{fileType}</span>
                  <span className="text-xs text-text-primary font-medium truncate max-w-[150px]" title={artifact}>
                    {fileName}
                  </span>
                  <div className="flex items-center gap-1">
                    {isPreviewable && (
                      <button
                        onClick={() => handlePreview(artifact)}
                        className="text-xs px-2 py-0.5 rounded text-accent-primary hover:bg-accent-primary/10 transition-colors"
                        title="Preview"
                      >
                        Preview
                      </button>
                    )}
                    {isKeynote && (
                      <button
                        onClick={() => handleReveal(artifact)}
                        className="text-xs px-2 py-0.5 rounded text-accent-primary hover:bg-accent-primary/10 transition-colors"
                        title="Open in Keynote"
                      >
                        Open
                      </button>
                    )}
                    <button
                      onClick={() => handleReveal(artifact)}
                      className="text-xs px-2 py-0.5 rounded text-text-muted hover:text-text-primary transition-colors"
                      title="Reveal in Finder"
                    >
                      Reveal
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
}

