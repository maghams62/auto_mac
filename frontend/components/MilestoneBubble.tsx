"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";

interface MilestoneBubbleProps {
  milestone: string;
  icon: string;
  visible: boolean;
  onComplete?: () => void;
}

export default function MilestoneBubble({
  milestone,
  icon,
  visible,
  onComplete,
}: MilestoneBubbleProps) {
  const [shouldShow, setShouldShow] = useState(visible);

  useEffect(() => {
    if (visible) {
      setShouldShow(true);
      // Auto-hide after 3 seconds
      const timer = setTimeout(() => {
        setShouldShow(false);
        onComplete?.();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [visible, onComplete]);

  if (!shouldShow) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: -20 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
        className="fixed top-24 left-1/2 transform -translate-x-1/2 z-40"
      >
        <div className="glass rounded-full px-4 py-2 border border-accent-cyan/35 shadow-glow-secondary flex items-center space-x-2.5">
          <span className="text-lg">{icon}</span>
          <span className="text-sm font-semibold text-foreground">{milestone}</span>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

