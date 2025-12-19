"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

export type FeedbackChoice = "positive" | "negative";

interface FeedbackBarProps {
  goal: string;
  planStatus: string;
  analytics?: {
    duration?: number;
    completionRate?: number;
    averageStepDuration?: number;
  } | null;
  isSubmitting?: boolean;
  onSubmit: (choice: FeedbackChoice, notes?: string) => Promise<void> | void;
}

export default function FeedbackBar({
  goal,
  planStatus,
  analytics,
  isSubmitting = false,
  onSubmit,
}: FeedbackBarProps) {
  const [mode, setMode] = useState<"idle" | "negative_detail">("idle");
  const [notes, setNotes] = useState("");

  const handlePositive = () => {
    if (isSubmitting) return;
    onSubmit("positive");
  };

  const handleNegative = () => {
    if (isSubmitting) return;
    if (mode === "idle") {
      setMode("negative_detail");
      return;
    }
    onSubmit("negative", notes.trim() || undefined);
  };

  const handleCancel = () => {
    if (isSubmitting) return;
    setMode("idle");
    setNotes("");
  };

  const renderAnalytics = () => {
    if (!analytics) return null;
    const seconds = analytics.duration ? Math.round(analytics.duration / 100) / 10 : null;
    const completionRate = typeof analytics.completionRate === "number"
      ? Math.round(analytics.completionRate)
      : null;

    return (
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
        {seconds !== null && (
          <span>
            Runtime: <span className="text-text-primary font-medium">{seconds.toFixed(1)}s</span>
          </span>
        )}
        {completionRate !== null && (
          <span>
            Steps completed:{" "}
            <span className="text-text-primary font-medium">{completionRate}%</span>
          </span>
        )}
      </div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 12 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "rounded-2xl border border-surface-outline/40 bg-surface-elevated/80 backdrop-blur-glass px-4 py-4",
        "shadow-soft"
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex-1 space-y-1">
          <p className="text-sm font-semibold text-text-primary">
            How did this automation go?
          </p>
          <p className="text-xs text-text-muted">
            {goal || "Unnamed task"} &middot; Final status:{" "}
            <span className="text-text-primary font-medium capitalize">{planStatus}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePositive}
            disabled={isSubmitting}
            className={cn(
              "flex items-center gap-2 rounded-full border border-surface-outline px-4 py-2 text-sm font-medium",
              "transition-opacity duration-150",
              "bg-surface hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed"
            )}
          >
            <span role="img" aria-label="Thumbs up">👍</span>
            {isSubmitting ? "Submitting..." : "Thumbs up"}
          </button>
          <button
            type="button"
            onClick={handleNegative}
            disabled={isSubmitting}
            className={cn(
              "flex items-center gap-2 rounded-full border border-surface-outline px-4 py-2 text-sm font-medium",
              "transition-opacity duration-150",
              "bg-surface hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed"
            )}
          >
            <span role="img" aria-label="Thumbs down">👎</span>
            {mode === "negative_detail" ? (isSubmitting ? "Submitting..." : "Submit issue") : "Thumbs down"}
          </button>
        </div>
      </div>

      {renderAnalytics()}

      <AnimatePresence>
        {mode === "negative_detail" && (
          <motion.div
            key="negative-detail"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-4 rounded-xl border border-warning-border/40 bg-warning-bg/20 p-3"
          >
            <p className="text-xs text-text-primary font-medium mb-2">
              Let us know what went wrong (optional):
            </p>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={3}
              placeholder="Briefly describe the issue or unexpected behavior..."
              className={cn(
                "w-full rounded-lg border border-surface-outline bg-surface px-3 py-2 text-sm text-text-primary",
                "focus:outline-none focus:ring-2 focus:ring-warning-border/60 focus:border-warning-border"
              )}
              disabled={isSubmitting}
            />
            <div className="mt-3 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={handleCancel}
                disabled={isSubmitting}
                className="text-xs font-medium text-text-muted hover:text-text-primary transition-colors disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleNegative}
                disabled={isSubmitting}
                className={cn(
                  "rounded-full border border-warning-border bg-warning-bg px-4 py-2 text-xs font-semibold text-warning",
                  "hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed"
                )}
              >
                {isSubmitting ? "Submitting..." : "Flag issue"}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
