"use client";

import React, { memo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * API change detected by the drift checker
 */
interface ApiChange {
  change_type: string;
  severity: "breaking" | "non_breaking" | "cosmetic";
  endpoint: string;
  description: string;
  code_value?: string;
  spec_value?: string;
}

/**
 * Drift report from the API diff service
 */
export interface ApidocsDriftReport {
  has_drift: boolean;
  changes: ApiChange[];
  summary: string;
  proposed_spec?: string;
  change_count: number;
  breaking_changes: number;
  non_breaking_changes?: number;
}

interface ApidocsDriftCardProps {
  driftReport: ApidocsDriftReport;
  onApprove?: (proposedSpec: string) => void;
  onDismiss?: () => void;
  onViewDocs?: () => void;
}

/**
 * Card component for displaying API documentation drift.
 * 
 * Implements the Oqoqo self-evolving docs pattern:
 * - Shows detected changes between code and docs
 * - Allows user to approve/dismiss updates
 * - Provides link to view documentation
 */
const ApidocsDriftCard = memo<ApidocsDriftCardProps>(
  ({ driftReport, onApprove, onDismiss, onViewDocs }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isApplying, setIsApplying] = useState(false);
    const [applied, setApplied] = useState(false);

    const handleApprove = async () => {
      if (!driftReport.proposed_spec || !onApprove) return;
      
      setIsApplying(true);
      try {
        await onApprove(driftReport.proposed_spec);
        setApplied(true);
      } catch (error) {
        console.error("Failed to apply spec update:", error);
      } finally {
        setIsApplying(false);
      }
    };

    const severityColors = {
      breaking: {
        bg: "bg-red-500/10",
        border: "border-red-500/30",
        text: "text-red-400",
        badge: "bg-red-500/20 text-red-300",
      },
      non_breaking: {
        bg: "bg-yellow-500/10",
        border: "border-yellow-500/30",
        text: "text-yellow-400",
        badge: "bg-yellow-500/20 text-yellow-300",
      },
      cosmetic: {
        bg: "bg-blue-500/10",
        border: "border-blue-500/30",
        text: "text-blue-400",
        badge: "bg-blue-500/20 text-blue-300",
      },
    };

    const hasBreakingChanges = driftReport.breaking_changes > 0;
    const cardColors = hasBreakingChanges ? severityColors.breaking : severityColors.non_breaking;

    if (applied) {
      return (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 p-4 bg-gradient-to-r from-green-500/10 via-emerald-500/10 to-green-500/10 border border-green-500/20 rounded-lg"
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">✅</span>
            <div>
              <p className="text-sm font-medium text-green-300">API Documentation Updated</p>
              <p className="text-xs text-green-400/70">
                The spec has been synced with your code. {driftReport.change_count} change(s) applied.
              </p>
            </div>
            {onViewDocs && (
              <button
                onClick={onViewDocs}
                className="ml-auto px-3 py-1.5 text-xs font-medium rounded bg-green-500/20 hover:bg-green-500/30 text-green-300 border border-green-500/30 transition-colors"
              >
                View Docs
              </button>
            )}
          </div>
        </motion.div>
      );
    }

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn(
          "mt-3 p-4 rounded-lg border",
          "bg-gradient-to-r",
          hasBreakingChanges
            ? "from-red-500/10 via-orange-500/10 to-red-500/10 border-red-500/20"
            : "from-yellow-500/10 via-amber-500/10 to-yellow-500/10 border-yellow-500/20"
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📄</span>
            <div>
              <div className="flex items-center gap-2">
                <p className={cn("text-sm font-semibold", cardColors.text)}>
                  API Documentation Drift Detected
                </p>
                {hasBreakingChanges && (
                  <span className="px-2 py-0.5 text-xs font-medium rounded bg-red-500/20 text-red-300 border border-red-500/30">
                    ⚠️ Breaking
                  </span>
                )}
              </div>
              <p className="text-xs text-white/60 mt-0.5">
                {driftReport.change_count} change{driftReport.change_count !== 1 ? "s" : ""} found
                {driftReport.breaking_changes > 0 && ` (${driftReport.breaking_changes} breaking)`}
              </p>
            </div>
          </div>

          {/* Expand/Collapse button */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 text-white/50 hover:text-white/80 transition-colors"
          >
            <svg
              className={cn("w-5 h-5 transition-transform", isExpanded && "rotate-180")}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        {/* Summary */}
        <div className="mb-3 p-3 bg-white/5 rounded border border-white/10">
          <p className="text-sm text-white/80 whitespace-pre-wrap">
            {driftReport.summary.split("\n").slice(0, isExpanded ? undefined : 3).join("\n")}
            {!isExpanded && driftReport.summary.split("\n").length > 3 && "..."}
          </p>
        </div>

        {/* Expanded: Show all changes */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="mb-3 space-y-2">
                <p className="text-xs font-medium text-white/60 uppercase tracking-wide">
                  Changes Detected
                </p>
                {driftReport.changes.map((change, idx) => {
                  const colors = severityColors[change.severity] || severityColors.cosmetic;
                  return (
                    <div
                      key={idx}
                      className={cn(
                        "p-2 rounded border",
                        colors.bg,
                        colors.border
                      )}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn("px-1.5 py-0.5 text-xs font-medium rounded", colors.badge)}>
                          {change.severity.replace("_", " ")}
                        </span>
                        <code className="text-xs text-white/70 font-mono">
                          {change.endpoint}
                        </code>
                      </div>
                      <p className={cn("text-xs", colors.text)}>
                        {change.description}
                      </p>
                      {(change.code_value || change.spec_value) && (
                        <div className="mt-1 text-xs text-white/50 font-mono">
                          {change.code_value && <div>Code: {change.code_value}</div>}
                          {change.spec_value && <div>Spec: {change.spec_value}</div>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2 border-t border-white/10">
          <p className="text-xs text-white/50 flex-1">
            Would you like to update the API documentation to match the code?
          </p>
          
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="px-3 py-1.5 text-xs font-medium rounded bg-white/10 hover:bg-white/20 text-white/70 hover:text-white border border-white/20 transition-colors"
            >
              Dismiss
            </button>
          )}
          
          {onApprove && driftReport.proposed_spec && (
            <button
              onClick={handleApprove}
              disabled={isApplying}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded transition-colors",
                hasBreakingChanges
                  ? "bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30"
                  : "bg-green-500/20 hover:bg-green-500/30 text-green-300 border border-green-500/30",
                isApplying && "opacity-50 cursor-not-allowed"
              )}
            >
              {isApplying ? "Applying..." : "Approve & Update"}
            </button>
          )}
          
          {onViewDocs && (
            <button
              onClick={onViewDocs}
              className="px-3 py-1.5 text-xs font-medium rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 border border-blue-500/30 transition-colors"
            >
              View Docs
            </button>
          )}
        </div>
      </motion.div>
    );
  }
);

ApidocsDriftCard.displayName = "ApidocsDriftCard";

export default ApidocsDriftCard;

