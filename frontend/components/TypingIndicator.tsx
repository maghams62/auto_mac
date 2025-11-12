"use client";

import { motion } from "framer-motion";
import { messageEntrance } from "@/lib/motion";
import { cn } from "@/lib/utils";

export default function TypingIndicator() {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      exit="hidden"
      variants={messageEntrance}
      className="flex justify-start mb-5"
    >
      <div className={cn(
        "max-w-[80%] rounded-lg px-5 py-3",
        "bg-glass-assistant backdrop-blur-glass shadow-inset-border"
      )}>
        {/* Shimmer effect background */}
        <div className="absolute inset-0 rounded-lg overflow-hidden pointer-events-none">
          <div
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent"
            style={{
              backgroundSize: "200% 100%",
              animation: "shimmer 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
            }}
          />
        </div>
        
        <div className="relative flex items-center space-x-2.5">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-2 h-2 bg-accent-primary rounded-full"
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
      </div>
    </motion.div>
  );
}
