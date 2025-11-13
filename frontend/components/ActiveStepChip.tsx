"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { PlanState } from "@/lib/useWebSocket";

interface ActiveStepChipProps {
  planState: PlanState | null;
  className?: string;
}

export default function ActiveStepChip({ planState, className }: ActiveStepChipProps) {
  if (!planState || !planState.activeStepId) return null;

  const activeStep = planState.steps.find(step => step.id === planState.activeStepId);
  if (!activeStep) return null;

  const getRunningIcon = () => (
    <motion.svg
      className="w-3 h-3"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      animate={{ rotate: 360 }}
      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </motion.svg>
  );

  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={activeStep.status === "running" ? {
        scale: 1.1,
        opacity: 1,
        boxShadow: [
          "0 0 25px rgba(59, 130, 246, 0.7), 0 0 50px rgba(59, 130, 246, 0.4), 0 0 75px rgba(59, 130, 246, 0.2)",
          "0 0 40px rgba(59, 130, 246, 1), 0 0 80px rgba(59, 130, 246, 0.6), 0 0 120px rgba(59, 130, 246, 0.3)",
          "0 0 25px rgba(59, 130, 246, 0.7), 0 0 50px rgba(59, 130, 246, 0.4), 0 0 75px rgba(59, 130, 246, 0.2)"
        ],
        borderColor: [
          "rgba(59, 130, 246, 0.3)",
          "rgba(59, 130, 246, 0.8)",
          "rgba(59, 130, 246, 0.3)"
        ]
      } : { scale: 1, opacity: 1 }}
      exit={{ scale: 0.8, opacity: 0 }}
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1.5 rounded-full",
        "bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium",
        "shadow-sm relative overflow-hidden",
        className
      )}
      transition={activeStep.status === "running" ? { duration: 2, repeat: Infinity, ease: "easeInOut" } : { duration: 0.3 }}
    >
      <motion.svg
        className="w-3 h-3"
        fill="currentColor"
        viewBox="0 0 24 24"
        animate={{ scale: [1, 1.2, 1] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        <path d="M8 5v14l11-7z" />
      </motion.svg>

      <span className="truncate max-w-48">{activeStep.action}</span>

      <motion.div
        className="flex gap-1"
        initial={{ opacity: 0.3 }}
        animate={{ opacity: [0.3, 1, 0.3] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        <div className="w-1 h-1 bg-blue-500 rounded-full" />
        <div className="w-1 h-1 bg-blue-500 rounded-full" />
        <div className="w-1 h-1 bg-blue-500 rounded-full" />
      </motion.div>
    </motion.div>
  );
}
