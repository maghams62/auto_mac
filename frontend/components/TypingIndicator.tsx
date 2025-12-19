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
      <motion.div
        className={cn(
          "relative max-w-[80%] rounded-full bg-white/8 px-4 py-2 backdrop-blur-glass shadow-inset-border overflow-hidden",
          "before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/10 before:to-transparent before:animate-shimmer"
        )}
        animate={{
          boxShadow: [
            "0 0 15px rgba(139, 92, 246, 0.3), 0 0 30px rgba(139, 92, 246, 0.1)",
            "0 0 25px rgba(139, 92, 246, 0.5), 0 0 50px rgba(139, 92, 246, 0.2)",
            "0 0 15px rgba(139, 92, 246, 0.3), 0 0 30px rgba(139, 92, 246, 0.1)"
          ]
        }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="flex items-center justify-center space-x-1 relative z-10">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="w-1 h-4 bg-accent-primary rounded-full"
              animate={{
                x: [-8, 8, -8],
                opacity: [0.5, 1, 0.5]
              }}
              transition={{
                duration: 1.4,
                repeat: Infinity,
                ease: "easeInOut",
                delay: i * 0.15,
                opacity: { duration: 1.4, repeat: Infinity, delay: i * 0.15 }
              }}
            />
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
