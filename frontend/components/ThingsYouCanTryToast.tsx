"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState, useRef } from "react";

interface WorkflowSuggestion {
  icon: string;
  text: string;
  command: string;
}

const WORKFLOW_SUGGESTIONS: WorkflowSuggestion[] = [
  { icon: "📈", text: "Get a stock report", command: "Get stock analysis for AAPL" },
  { icon: "📁", text: "Summarize a PDF", command: "Summarize the document about" },
  { icon: "✈️", text: "Plan a trip", command: "Plan a trip from" },
  { icon: "📊", text: "Create presentation", command: "Create a Keynote presentation about" },
  { icon: "🔍", text: "Search documents", command: "Search my documents for" },
  { icon: "📧", text: "Send email", command: "Send an email to" },
];

interface ThingsYouCanTryToastProps {
  onSelectSuggestion: (command: string) => void;
  idleTimeMs?: number;
  onUserActivity?: () => void;
}

export default function ThingsYouCanTryToast({
  onSelectSuggestion,
  idleTimeMs = 10000, // 10 seconds default
  onUserActivity,
}: ThingsYouCanTryToastProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);
  const [suggestion, setSuggestion] = useState<WorkflowSuggestion | null>(null);
  const lastActivityRef = useRef<number>(Date.now());

  // Reset on user activity
  useEffect(() => {
    const handleActivity = () => {
      lastActivityRef.current = Date.now();
      setIsVisible(false);
      setIsDismissed(false);
    };

    // Listen for various user activities
    window.addEventListener("mousedown", handleActivity);
    window.addEventListener("keydown", handleActivity);
    window.addEventListener("scroll", handleActivity);

    return () => {
      window.removeEventListener("mousedown", handleActivity);
      window.removeEventListener("keydown", handleActivity);
      window.removeEventListener("scroll", handleActivity);
    };
  }, []);

  useEffect(() => {
    if (isDismissed) return;

    const checkIdle = () => {
      const timeSinceActivity = Date.now() - lastActivityRef.current;
      if (timeSinceActivity >= idleTimeMs && !isVisible) {
        // Pick a random suggestion
        const randomSuggestion =
          WORKFLOW_SUGGESTIONS[
            Math.floor(Math.random() * WORKFLOW_SUGGESTIONS.length)
          ];
        setSuggestion(randomSuggestion);
        setIsVisible(true);
      }
    };

    const interval = setInterval(checkIdle, 1000);
    return () => clearInterval(interval);
  }, [idleTimeMs, isDismissed, isVisible]);

  const handleDismiss = () => {
    lastActivityRef.current = Date.now();
    setIsVisible(false);
    setIsDismissed(true);
    onUserActivity?.();
  };

  const handleSelect = () => {
    if (suggestion) {
      lastActivityRef.current = Date.now();
      onSelectSuggestion(suggestion.command);
      setIsVisible(false);
      setIsDismissed(true);
      onUserActivity?.();
    }
  };

  if (!isVisible || !suggestion || isDismissed) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 20 }}
        transition={{ duration: 0.3 }}
        className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-40"
      >
        <div className="glass rounded-xl px-4 py-3 border border-white/20 shadow-lg backdrop-blur-xl flex items-center space-x-3 max-w-md">
          <span className="text-xl">{suggestion.icon}</span>
          <div className="flex-1">
            <p className="text-xs text-white/60 mb-1">Things you can try:</p>
            <button
              onClick={handleSelect}
              className="text-sm font-medium text-white hover:text-accent-cyan transition-colors text-left"
            >
              {suggestion.text}
            </button>
          </div>
          <button
            onClick={handleDismiss}
            className="text-white/40 hover:text-white/80 transition-colors"
            aria-label="Dismiss"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

