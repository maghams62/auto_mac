"use client";

import { useState, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fadeIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface HelpTooltipProps {
  content: string;
  shortcut?: string;
  children: ReactNode;
  delay?: number;
}

export default function HelpTooltip({
  content,
  shortcut,
  children,
  delay = 300,
}: HelpTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [timeoutId, setTimeoutId] = useState<NodeJS.Timeout | null>(null);

  const handleMouseEnter = () => {
    const id = setTimeout(() => {
      setIsVisible(true);
    }, delay);
    setTimeoutId(id);
  };

  const handleMouseLeave = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
      setTimeoutId(null);
    }
    setIsVisible(false);
  };

  return (
    <div
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      <AnimatePresence>
        {isVisible && (
          <motion.div
            initial="hidden"
            animate="visible"
            exit="hidden"
            variants={fadeIn}
            className={cn(
              "absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50",
              "px-3 py-2 rounded-lg",
              "bg-glass-elevated backdrop-blur-glass border border-glass",
              "shadow-elevated text-xs text-text-primary",
              "whitespace-nowrap pointer-events-none"
            )}
          >
            <div className="flex flex-col gap-1">
              <span>{content}</span>
              {shortcut && (
                <span className="text-text-subtle font-mono">{shortcut}</span>
              )}
            </div>
            {/* Arrow */}
            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px">
              <div className="w-2 h-2 bg-glass-elevated border-r border-b border-glass rotate-45" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

