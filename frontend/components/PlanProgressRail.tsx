"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { PlanState } from "@/lib/useWebSocket";

interface PlanProgressRailProps {
  planState: PlanState | null;
  onToggleCollapse?: () => void;
  onToggleReasoningTrace?: () => void;
  isCollapsed?: boolean;
  showReasoningTrace?: boolean;
}

// Icon components using inline SVGs
const ChevronUpIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
  </svg>
);

const ChevronDownIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
);

const ClockIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <circle cx={12} cy={12} r={10} />
    <polyline points="12,6 12,12 16,14" />
  </svg>
);

const CheckCircleIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22,4 12,14.01 9,11.01" />
  </svg>
);

const XCircleIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <circle cx={12} cy={12} r={10} />
    <line x1={15} y1={9} x2={9} y2={15} />
    <line x1={9} y1={9} x2={15} y2={15} />
  </svg>
);

const PlayCircleIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <circle cx={12} cy={12} r={10} />
    <polygon points="10,8 16,12 10,16 10,8" />
  </svg>
);

const SkipForwardIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <polygon points="5,4 15,12 5,20 5,4" />
    <line x1={19} y1={5} x2={19} y2={19} />
  </svg>
);

const EyeIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
  </svg>
);

export default function PlanProgressRail({
  planState,
  onToggleCollapse,
  onToggleReasoningTrace,
  isCollapsed = false,
  showReasoningTrace = false
}: PlanProgressRailProps) {
  const [showRail, setShowRail] = useState(false);

  useEffect(() => {
    // Show rail when plan is active
    setShowRail(planState !== null && planState.status === "executing");
  }, [planState]);

  if (!planState || !showRail) return null;

  const completedSteps = planState.steps.filter(step => step.status === "completed").length;
  const totalSteps = planState.steps.length;
  const progressPercentage = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <PlayCircleIcon className="w-4 h-4 text-accent-primary animate-pulse" />;
      case "completed":
        return <CheckCircleIcon className="w-4 h-4 text-success" />;
      case "failed":
        return <XCircleIcon className="w-4 h-4 text-accent-danger" />;
      case "skipped":
        return <SkipForwardIcon className="w-4 h-4 text-text-muted" />;
      default:
        return <ClockIcon className="w-4 h-4 text-text-muted" />;
    }
  };

const getStatusColor = (status: string) => {
  switch (status) {
    case "running":
      return "border-accent-primary/60 bg-accent-primary/10 text-accent-primary";
    case "completed":
      return "border-success-border bg-success-bg text-success";
    case "failed":
      return "border-danger-border bg-danger-bg text-accent-danger";
    case "skipped":
      return "border-surface-outline/60 bg-surface/60 text-text-muted";
    default:
      return "border-surface-outline/40 bg-surface/50 text-text-muted";
  }
};

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -100, opacity: 0 }}
        className="fixed top-0 left-0 right-0 z-50 bg-surface/90 backdrop-blur-md border-b border-surface-outline/40 shadow-soft"
      >
        <div className="max-w-4xl mx-auto px-4 py-3 text-text-primary">
          {/* Header with goal and progress */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="text-sm font-medium text-text-primary truncate">
                🎯 {planState.goal}
              </div>
              <div className="text-xs text-text-muted">
                {completedSteps}/{totalSteps} steps
              </div>
            </div>

            <div className="flex items-center gap-2">
              {onToggleReasoningTrace && (
                <button
                  onClick={onToggleReasoningTrace}
                  className={cn(
                    "flex items-center gap-1 text-xs transition-colors px-2 py-1 rounded",
                    showReasoningTrace
                      ? "text-accent-primary bg-accent-primary/15 hover:bg-accent-primary/20"
                      : "text-text-muted hover:text-text-primary hover:bg-surface/60"
                  )}
                  title={showReasoningTrace ? "Hide detailed reasoning trace" : "Show detailed reasoning trace"}
                >
                  <EyeIcon className="w-3 h-3" />
                  Trace
                </button>
              )}

              <button
                onClick={onToggleCollapse}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors px-2 py-1 rounded hover:bg-surface/60"
              >
                {isCollapsed ? (
                  <>
                    <ChevronDownIcon className="w-3 h-3" />
                    Expand
                  </>
                ) : (
                  <>
                    <ChevronUpIcon className="w-3 h-3" />
                    Collapse
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-surface-outline/40 rounded-full h-2 mb-3">
            <motion.div
              className="bg-gradient-to-r from-blue-500 to-green-500 h-2 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progressPercentage}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>

          {/* Steps - conditionally shown */}
          <AnimatePresence>
            {!isCollapsed && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="flex flex-wrap gap-2 relative">
                  {planState.steps.map((step, index) => (
                    <React.Fragment key={step.id}>
                      {/* Connecting line to next step */}
                      {index < planState.steps.length - 1 && (
                        <motion.div
                          className="absolute h-0.5 rounded-full"
                          style={{
                            top: '50%',
                            left: '100%',
                            width: '12px',
                            transform: 'translateY(-50%)',
                            zIndex: 0,
                            background: step.status === "completed"
                              ? 'linear-gradient(to right, rgba(59, 130, 246, 0.8), rgba(59, 130, 246, 0.6))'
                              : step.status === "running"
                              ? 'linear-gradient(to right, rgba(59, 130, 246, 0.6), rgba(59, 130, 246, 0.4))'
                              : 'linear-gradient(to right, rgba(59, 130, 246, 0.2), rgba(59, 130, 246, 0.1))'
                          }}
                          initial={{ scaleX: 0, opacity: 0 }}
                          animate={{
                            scaleX: step.status === "completed" ? 1 : step.status === "running" ? 0.7 : 0,
                            opacity: step.status === "completed" ? 1 : step.status === "running" ? 0.7 : 0
                          }}
                          transition={{
                            duration: step.status === "completed" ? 0.8 : 0.4,
                            delay: step.status === "completed" ? index * 0.1 + 0.2 : 0,
                            ease: "easeOut"
                          }}
                        />
                      )}

                      <motion.div
                      key={step.id}
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{
                        scale: step.status === "running" ? 1.15 : step.status === "completed" ? [1.15, 1] : 1,
                        opacity: 1,
                        boxShadow: step.status === "running" ? [
                          "0 0 30px rgba(59, 130, 246, 0.7), 0 0 60px rgba(59, 130, 246, 0.4), 0 0 90px rgba(59, 130, 246, 0.2)",
                          "0 0 50px rgba(59, 130, 246, 1), 0 0 100px rgba(59, 130, 246, 0.6), 0 0 150px rgba(59, 130, 246, 0.3)",
                          "0 0 30px rgba(59, 130, 246, 0.7), 0 0 60px rgba(59, 130, 246, 0.4), 0 0 90px rgba(59, 130, 246, 0.2)"
                        ] : step.status === "completed" ? "0 0 15px rgba(34, 197, 94, 0.5)" : "0 0 0px rgba(59, 130, 246, 0)"
                      }}
                      transition={{
                        delay: index * 0.1,
                        scale: step.status === "running" ? { duration: 1.5, repeat: Infinity, ease: "easeInOut" } :
                              step.status === "completed" ? { duration: 0.5, type: "spring", bounce: 0.3 } : { duration: 0.3 },
                        boxShadow: step.status === "running" ? { duration: 2, repeat: Infinity, ease: "easeInOut" } : { duration: 0.3 }
                      }}
                      className={cn(
                        "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium",
                        "border transition-all duration-300 relative overflow-hidden shadow-soft/40",
                        getStatusColor(step.status),
                        step.status === "running" && "ring-4 ring-accent-primary/60 scale-110"
                      )}
                    >
                      {getStatusIcon(step.status)}
                      <span className="truncate max-w-32">{step.action}</span>
                      {step.status === "running" && (
                        <motion.div
                          className="w-1 h-1 bg-blue-500 rounded-full"
                          animate={{ scale: [1, 1.5, 1] }}
                          transition={{ duration: 1, repeat: Infinity }}
                        />
                      )}
                      </motion.div>
                    </React.Fragment>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
