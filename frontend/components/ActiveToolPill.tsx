"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface ActiveToolPillProps {
  toolName?: string;
  visible: boolean;
}

export default function ActiveToolPill({ toolName, visible }: ActiveToolPillProps) {
  const [displayName, setDisplayName] = useState<string>("");
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const startTimeRef = useRef<number | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (toolName) {
      // Format tool name: "create_zip_archive" -> "create_zip_archive"
      const formatted = toolName
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
      setDisplayName(formatted);
    }
  }, [toolName]);

  // Track elapsed time
  useEffect(() => {
    if (visible && toolName) {
      // Start tracking time
      startTimeRef.current = Date.now();
      setElapsedSeconds(0);

      // Update every second
      intervalRef.current = setInterval(() => {
        if (startTimeRef.current) {
          const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
          setElapsedSeconds(elapsed);
        }
      }, 1000);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    } else {
      // Stop tracking
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      startTimeRef.current = null;
      setElapsedSeconds(0);
    }
  }, [visible, toolName]);

  if (!visible || !toolName) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -20, scale: 0.95 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="fixed top-20 left-1/2 transform -translate-x-1/2 z-50"
      >
        <div className="glass rounded-full px-4 py-2 border border-accent-cyan/35 shadow-glow-secondary">
          <div className="flex items-center space-x-2.5">
            <motion.div 
              className="w-2 h-2 bg-accent-cyan rounded-full"
              animate={{
                scale: [1, 1.3, 1],
                opacity: [0.8, 1, 0.8],
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
            <span className="text-sm font-semibold text-foreground">
              {displayName}
            </span>
            {elapsedSeconds > 0 && (
              <span className="text-xs text-foreground-muted font-medium">
                – {elapsedSeconds}s
              </span>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

