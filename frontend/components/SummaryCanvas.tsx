"use client";

import { useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { overlayFade, modalSlideDown } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface SummaryCanvasProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  summary: string;
  message?: string;
}

export default function SummaryCanvas({
  isOpen,
  onClose,
  title,
  summary,
  message,
}: SummaryCanvasProps) {
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Extract a better title from the summary if not provided
  const displayTitle = useMemo(() => {
    if (title) return title;

    // Try to extract title from message or summary
    const source = message || summary;
    const firstSentence = source.split(/[.!?]/)[0].trim();

    // If first sentence is short and looks like a title, use it
    if (firstSentence.length < 60 && firstSentence.length > 0) {
      return firstSentence;
    }
    
    return "Summary";
  }, [title, message, summary]);

  // Prevent body scroll when canvas is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  // Split summary into paragraphs for better formatting
  const paragraphs = summary.split("\n\n").filter((p) => p.trim());

  return (
    <AnimatePresence>
      <motion.div
        initial="hidden"
        animate="visible"
        exit="hidden"
        variants={overlayFade}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Backdrop with blur */}
        <div className="absolute inset-0 bg-black/60 backdrop-blur-md" />

        {/* Canvas Window */}
        <motion.div
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={modalSlideDown}
          className={cn(
            "relative w-full max-w-4xl max-h-[90vh] overflow-hidden",
            "bg-gradient-to-br from-neutral-900/95 via-neutral-800/95 to-neutral-900/95",
            "backdrop-blur-xl rounded-2xl",
            "border border-white/10 shadow-2xl",
            "flex flex-col"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/5">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-accent-primary/60 animate-pulse" />
              <h2 className="text-xl font-semibold text-text-primary">
                {displayTitle}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-primary transition-colors p-1 rounded-lg hover:bg-white/5"
              aria-label="Close"
            >
              <svg
                className="w-5 h-5"
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

          {/* Content Area */}
          <div className="flex-1 overflow-y-auto px-6 py-6">
            {/* Message if provided */}
            {message && (
              <div className="mb-6 pb-6 border-b border-white/10">
                <p className="text-text-muted text-sm font-medium mb-2">Message</p>
                <p className="text-text-primary leading-relaxed">{message}</p>
              </div>
            )}

            {/* Summary Content */}
            <div className="prose prose-invert max-w-none">
              {paragraphs.length > 0 ? (
                paragraphs.map((paragraph, index) => (
                  <p
                    key={index}
                    className="text-text-primary leading-relaxed mb-4 text-base first:mt-0"
                    style={{ textAlign: "left" }}
                  >
                    {paragraph.trim()}
                  </p>
                ))
              ) : (
                <p className="text-text-primary leading-relaxed">{summary}</p>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-white/10 bg-white/5 flex items-center justify-between">
            <div className="text-xs text-text-muted">
              Press <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-text-muted">ESC</kbd> to close
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-accent-primary/20 hover:bg-accent-primary/30 text-accent-primary rounded-lg transition-colors text-sm font-medium"
            >
              Close
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

