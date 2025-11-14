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
        return "border-blue-500 bg-blue-50/50";
      case "completed":
        return "border-green-500 bg-green-50/50";
      case "failed":
        return "border-red-500 bg-red-50/50";
      case "skipped":
        return "border-gray-400 bg-gray-50/50";
      default:
        return "border-gray-300 bg-gray-50/50";
    }
  };

  const getTimelineColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-blue-500";
      case "completed":
        return "bg-green-500";
      case "failed":
        return "bg-red-500";
      case "skipped":
        return "bg-gray-400";
      default:
        return "bg-gray-300";
    }
  };

  return (
    <div className={cn("w-full max-w-2xl mx-auto", className)}>
      <div className="space-y-4">
        {planState.steps.map((step, index) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="relative"
          >
            {/* Timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-200 -z-10">
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
                "flex items-start gap-4 p-4 rounded-lg border transition-all duration-300",
                getStatusColor(step.status),
                step.status === "running" && "ring-2 ring-blue-500/30"
              )}
              animate={step.status === "running" ? {
                boxShadow: [
                  "0 0 20px rgba(59, 130, 246, 0.3)",
                  "0 0 40px rgba(59, 130, 246, 0.5)",
                  "0 0 20px rgba(59, 130, 246, 0.3)"
                ]
              } : {}}
              transition={step.status === "running" ? {
                duration: 2,
                repeat: Infinity,
                ease: "easeInOut"
              } : {}}
            >
              {/* Status icon */}
              <div className="flex-shrink-0 w-12 h-12 rounded-full bg-white border-2 border-gray-200 flex items-center justify-center shadow-sm">
                {getStatusIcon(step.status)}
              </div>

              {/* Step content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">
                      Step {step.id}: {step.action}
                    </span>
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
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
                <div className="mt-2 text-sm text-gray-600">
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
                      <div className="text-sm text-gray-600">
                        <strong>Expected Output:</strong> {step.expected_output}
                      </div>

                      {/* Parameters */}
                      {step.parameters && Object.keys(step.parameters).length > 0 && (
                        <div className="text-sm text-gray-600">
                          <strong>Parameters:</strong>
                          <pre className="mt-1 text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                            {JSON.stringify(step.parameters, null, 2)}
                          </pre>
                        </div>
                      )}

                      {/* Dependencies */}
                      {step.dependencies && step.dependencies.length > 0 && (
                        <div className="text-sm text-gray-600">
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