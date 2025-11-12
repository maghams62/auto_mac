"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { scaleIn } from "@/lib/motion";

interface TimelineStepProps {
  steps: Array<{
    id?: number;
    action: string;
    reasoning?: string;
  }>;
  activeStepIndex?: number;
  goal?: string;
}

export default function TimelineStep({ steps, activeStepIndex, goal }: TimelineStepProps) {
  return (
    <div className="space-y-3">
      {goal && (
        <div className="text-text-primary font-semibold mb-3 text-base">
          🎯 {goal}
        </div>
      )}
      
      <div className="flex flex-wrap items-center gap-2">
        {steps.map((step, idx) => {
          const isActive = activeStepIndex !== undefined && idx === activeStepIndex;
          const isCompleted = activeStepIndex !== undefined && idx < activeStepIndex;
          
          return (
            <motion.div
              key={step.id || idx}
              initial="hidden"
              animate="visible"
              variants={scaleIn}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 rounded-full",
                "bg-glass-assistant backdrop-blur-glass shadow-inset-border",
                "border transition-all duration-150",
                isActive && "border-accent-primary shadow-glow-primary",
                isCompleted && "border-glass opacity-75",
                !isActive && !isCompleted && "border-glass"
              )}
            >
              {idx > 0 && (
                <span className="text-text-muted text-xs">▸</span>
              )}
              <span className={cn(
                "text-sm font-medium",
                isActive && "text-accent-primary",
                isCompleted && "text-text-muted",
                !isActive && !isCompleted && "text-text-primary"
              )}>
                {step.action}
              </span>
              {isActive && (
                <motion.div
                  className="w-1.5 h-1.5 bg-accent-primary rounded-full"
                  animate={{ scale: [1, 1.2, 1], opacity: [1, 0.7, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

