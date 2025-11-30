"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { PlanState } from "@/lib/useWebSocket";

interface ReasoningTraceProps {
  planState: PlanState | null;
  className?: string;
}

// Icon components using inline SVGs
const ChevronDownIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
);

const ChevronUpIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
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

export default function ReasoningTrace({ planState, className }: ReasoningTraceProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  if (!planState) return null;

  const toggleStepExpansion = (stepId: number) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepId)) {
      newExpanded.delete(stepId);
    } else {
      newExpanded.add(stepId);
    }
    setExpandedSteps(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <PlayCircleIcon className="w-4 h-4 text-blue-500 animate-pulse" />;
      case "completed":
        return <CheckCircleIcon className="w-4 h-4 text-green-500" />;
      case "failed":
        return <XCircleIcon className="w-4 h-4 text-red-500" />;
      case "skipped":
        return <SkipForwardIcon className="w-4 h-4 text-gray-400" />;
      default:
        return <ClockIcon className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "border-blue-400/60 bg-blue-500/10";
      case "completed":
        return "border-green-400/60 bg-green-500/10";
      case "failed":
        return "border-red-400/60 bg-red-500/10";
      case "skipped":
        return "border-white/10 bg-white/5";
      default:
        return "border-white/10 bg-white/5";
    }
  };

  const getTimelineColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-blue-400";
      case "completed":
        return "bg-green-400";
      case "failed":
        return "bg-red-400";
      case "skipped":
        return "bg-white/20";
      default:
        return "bg-white/10";
    }
  };

  return (
    <div className={cn("w-full max-w-2xl mx-auto rounded-2xl border border-surface-outline/40 bg-surface/95 backdrop-blur-lg shadow-2xl p-4", className)}>
      <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
        {planState.steps.map((step, index) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="relative"
          >
            {/* Timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-white/10 -z-10">
              <motion.div
                className={cn("w-full", getTimelineColor(step.status))}
                initial={{ height: 0 }}
                animate={{
                  height: step.status === "completed" ? "100%" :
                          step.status === "running" ? "60%" : "0%"
                }}
                transition={{ duration: 0.8, delay: index * 0.1 }}
              />
            </div>

            {/* Step node */}
            <motion.div
              className={cn(
                "flex items-start gap-4 p-4 rounded-xl border transition-colors duration-300 bg-white/5",
                getStatusColor(step.status)
              )}
            >
              {/* Status icon */}
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-white/10 border border-white/15 flex items-center justify-center">
                {getStatusIcon(step.status)}
              </div>

              {/* Step content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white">
                      Step {step.id}: {step.action}
                    </span>
                    <span className="text-xs text-white/60 bg-white/10 px-2 py-0.5 rounded">
                      {step.status}
                    </span>
                  </div>

                  {/* Expand/collapse button */}
                  <button
                    onClick={() => toggleStepExpansion(step.id)}
                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors p-1 rounded hover:bg-gray-100"
                  >
                    {expandedSteps.has(step.id) ? (
                      <>
                        <ChevronUpIcon className="w-3 h-3" />
                        Collapse
                      </>
                    ) : (
                      <>
                        <ChevronDownIcon className="w-3 h-3" />
                        Details
                      </>
                    )}
                  </button>
                </div>

                {/* Step reasoning - always visible */}
                <div className="mt-2 text-sm text-white/70">
                  <strong>Reasoning:</strong> {step.reasoning}
                </div>

                {/* Expandable details */}
                <AnimatePresence>
                  {expandedSteps.has(step.id) && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="mt-3 space-y-2 overflow-hidden"
                    >
                      <div className="text-sm text-white/70">
                        <strong>Expected Output:</strong> {step.expected_output}
                      </div>

                      {/* Parameters */}
                      {step.parameters && Object.keys(step.parameters).length > 0 && (
                        <div className="text-sm text-white/70">
                          <strong>Parameters:</strong>
                          <pre className="mt-1 text-xs bg-black/30 p-2 rounded overflow-x-auto text-white/80 border border-white/10">
                            {JSON.stringify(step.parameters, null, 2)}
                          </pre>
                        </div>
                      )}

                      {/* Dependencies */}
                      {step.dependencies && step.dependencies.length > 0 && (
                        <div className="text-sm text-white/70">
                          <strong>Dependencies:</strong> Steps {step.dependencies.join(", ")}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}