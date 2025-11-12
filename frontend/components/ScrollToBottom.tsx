"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fadeIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface ScrollToBottomProps {
  containerRef: React.RefObject<HTMLElement>;
}

export default function ScrollToBottom({ containerRef }: ScrollToBottomProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const checkScrollPosition = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 100; // 100px threshold
      setIsVisible(!isAtBottom);
    };

    container.addEventListener("scroll", checkScrollPosition);
    checkScrollPosition(); // Initial check

    return () => {
      container.removeEventListener("scroll", checkScrollPosition);
    };
  }, [containerRef]);

  const scrollToBottom = () => {
    const container = containerRef.current;
    if (!container) return;

    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth",
    });
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.button
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={fadeIn}
          onClick={scrollToBottom}
          className={cn(
            "fixed bottom-24 right-6 z-40 p-3 rounded-full",
            "bg-glass-elevated backdrop-blur-glass shadow-elevated",
            "border border-glass shadow-inset-border",
            "hover:bg-glass-hover transition-colors",
            "text-text-primary"
          )}
          aria-label="Scroll to bottom"
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
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </motion.button>
      )}
    </AnimatePresence>
  );
}

