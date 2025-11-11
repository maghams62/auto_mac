"use client";

import { motion } from "framer-motion";

export default function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className="flex justify-start mb-4"
    >
      <div className="message-assistant max-w-[80%] rounded-2xl px-6 py-4 backdrop-blur-xl">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-white/60 rounded-full typing-dot" />
          <div className="w-2 h-2 bg-white/60 rounded-full typing-dot" />
          <div className="w-2 h-2 bg-white/60 rounded-full typing-dot" />
        </div>
      </div>
    </motion.div>
  );
}
