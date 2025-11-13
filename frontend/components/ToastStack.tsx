"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useToast, Toast } from "@/lib/useToast";
import { toastSlideIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

function ToastItem({ toast }: { toast: Toast }) {
  const { removeToast } = useToast();

  const variantStyles = {
    success: "bg-success-bg border-success-border text-accent-success",
    error: "bg-danger-bg border-danger-border text-accent-danger",
    warning: "bg-warning-bg border-warning-border text-accent-warning",
    info: "bg-glass-assistant border-glass text-text-primary",
  };

  const icons = {
    success: "✅",
    error: "❌",
    warning: "⚠️",
    info: "ℹ️",
  };

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      exit="exit"
      variants={toastSlideIn}
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg",
        "backdrop-blur-glass shadow-elevated border",
        variantStyles[toast.variant],
        "min-w-[300px] max-w-[400px]"
      )}
    >
      <span className="text-lg flex-shrink-0">{icons[toast.variant]}</span>
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="flex-shrink-0 text-text-muted hover:text-text-primary transition-colors"
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
    </motion.div>
  );
}

export default function ToastStack() {
  const { toasts } = useToast();

  return (
    <div className="fixed bottom-6 right-6 z-40 flex flex-col gap-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}

