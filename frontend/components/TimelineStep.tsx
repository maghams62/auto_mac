"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { scaleIn } from "@/lib/motion";
import { PlanState } from "@/lib/useWebSocket";

interface TimelineStepProps {
  // Legacy interface for backward compatibility
  steps?: Array<{
    id?: number;
    action: string;
    reasoning?: string;
  }>;
  activeStepIndex?: number;
  goal?: string;

  // New interface for live plan streaming
  planState?: PlanState | null;
}

export default function TimelineStep({ steps, activeStepIndex, goal, planState }: TimelineStepProps) {
  // Use planState if available, otherwise fall back to legacy props
  const displayGoal = planState?.goal || goal || "";
  const displaySteps = planState?.steps || steps || [];

  // For legacy compatibility, determine active step from activeStepIndex
  const activeStepId = planState?.activeStepId;
  return (
    <div className="space-y-3">
      {displayGoal && (
        <div className="text-text-primary font-semibold mb-3 text-base">
          🎯 {displayGoal}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {displaySteps.map((step, idx) => {
          // Handle both legacy and new step formats
          const stepId = step.id || idx;
          const stepAction = step.action;
          const stepStatus = 'status' in step ? step.status : 'pending';

          // Determine status for styling
          let isActive = false;
          let isCompleted = false;
          let isFailed = false;
          let isSkipped = false;

          if (planState) {
            // New planState-based logic
            isActive = stepStatus === 'running' || activeStepId === stepId;
            isCompleted = stepStatus === 'completed';
            isFailed = stepStatus === 'failed';
            isSkipped = stepStatus === 'skipped';
          } else {
            // Legacy logic for backward compatibility
            isActive = activeStepIndex !== undefined && idx === activeStepIndex;
            isCompleted = activeStepIndex !== undefined && idx < activeStepIndex;
          }

          return (
            <motion.div
              key={stepId}
              initial="hidden"
              animate="visible"
              variants={scaleIn}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 rounded-full",
                "bg-glass-assistant backdrop-blur-glass shadow-inset-border",
                "border transition-all duration-150",
                isActive && "border-accent-primary shadow-glow-primary",
                isCompleted && "border-green-500 bg-green-500/10 opacity-75",
                isFailed && "border-red-500 bg-red-500/10",
                isSkipped && "border-gray-500 bg-gray-500/10 opacity-50",
                !isActive && !isCompleted && !isFailed && !isSkipped && "border-glass"
              )}
            >
              {idx > 0 && (
                <span className="text-text-muted text-xs">▸</span>
              )}
              <span className={cn(
                "text-sm font-medium",
                isActive && "text-accent-primary",
                isCompleted && "text-green-600",
                isFailed && "text-red-600",
                isSkipped && "text-gray-500",
                !isActive && !isCompleted && !isFailed && !isSkipped && "text-text-primary"
              )}>
                {stepAction}
              </span>

              {/* Status indicators */}
              {isActive && (
                <motion.div
                  className="w-1.5 h-1.5 bg-accent-primary rounded-full"
                  animate={{ scale: [1, 1.2, 1], opacity: [1, 0.7, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
              {isCompleted && (
                <span className="text-green-600 text-xs">✓</span>
              )}
              {isFailed && (
                <span className="text-red-600 text-xs">✗</span>
              )}
              {isSkipped && (
                <span className="text-gray-500 text-xs">⊘</span>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Show plan status if available */}
      {planState && planState.status && (
        <div className="text-xs text-text-muted mt-2">
          Status: {planState.status}
          {planState.activeStepId && ` | Active: Step ${planState.activeStepId}`}
        </div>
      )}
    </div>
  );
}

