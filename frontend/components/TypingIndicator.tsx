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
        <div className="flex items-center space-x-2.5">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-2 h-2 bg-accent-primary rounded-full"
              animate={{
                opacity: [0.4, 1, 0.4],
                scale: [0.8, 1.2, 0.8],
              }}
              transition={{
                duration: 0.1, // duration.fast
                repeat: Infinity,
                delay: i * 0.05,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
