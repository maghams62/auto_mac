"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface StatusRowProps {
  status: string;
  className?: string;
}

export default function StatusRow({ status, className }: StatusRowProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.15, ease: [0.25, 0.1, 0.25, 1] }}
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1.5 rounded-full",
        "bg-glass-assistant backdrop-blur-glass shadow-inset-border",
        "border border-glass",
        className
      )}
    >
      {/* Shimmer effect background */}
      <div className="absolute inset-0 rounded-full overflow-hidden">
        <div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent"
          style={{
            backgroundSize: "200% 100%",
            animation: "shimmer 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
          }}
        />
      </div>
      
      {/* Bouncing dots */}
      <div className="relative flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-1.5 h-1.5 bg-accent-primary rounded-full"
            animate={{
              scale: [0, 1, 0],
              opacity: [0.5, 1, 0.5],
            }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              delay: i * 0.2,
              ease: [0.68, -0.55, 0.265, 1.55],
            }}
          />
        ))}
      </div>
      
      {/* Status text */}
      <span className="relative text-xs font-medium text-text-primary">
        {status}
      </span>
    </motion.div>
  );
}

