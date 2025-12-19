"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Message } from "@/lib/useWebSocket";

interface TranscriptsPaneProps {
  messages: Message[];
  onScrollToMessage: (index: number) => void;
}

export default function TranscriptsPane({ messages, onScrollToMessage }: TranscriptsPaneProps) {
  // Extract user commands with their status
  const transcripts = useMemo(() => {
    const userMessages = messages
      .map((msg, idx) => ({ msg, idx }))
      .filter(({ msg }) => msg.type === "user");
    
    return userMessages.map(({ msg, idx }) => {
      // Find the next assistant/error/plan message to determine status
      const nextResponse = messages.slice(idx + 1).find(
        (m) => m.type === "assistant" || m.type === "error" || m.type === "plan"
      );
      
      let status: "pending" | "success" | "error" | "processing" = "pending";
      let statusIcon = "⏳";
      
      if (nextResponse) {
        if (nextResponse.type === "error") {
          status = "error";
          statusIcon = "❌";
        } else if (nextResponse.type === "plan") {
          status = "processing";
          statusIcon = "🔄";
        } else if (nextResponse.type === "assistant") {
          status = "success";
          statusIcon = "✅";
        }
      }
      
      // Check if there's a status message indicating processing
      const hasProcessingStatus = messages.slice(idx + 1).some(
        (m) => m.type === "status" && m.status === "processing"
      );
      if (hasProcessingStatus && status === "pending") {
        status = "processing";
        statusIcon = "🔄";
      }
      
      return {
        command: msg.message,
        index: idx,
        status,
        statusIcon,
        timestamp: msg.timestamp,
      };
    }).slice(-10).reverse(); // Last 10 commands, most recent first
  }, [messages]);

  if (transcripts.length === 0) {
    return (
      <div className="p-4 text-center text-white/40 text-sm">
        No commands yet
      </div>
    );
  }

  return (
    <div className="p-2 space-y-1">
      {transcripts.map((transcript) => (
        <motion.button
          key={transcript.index}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          onClick={() => onScrollToMessage(transcript.index)}
          className={cn(
            "w-full text-left px-2 py-1.5 rounded-lg text-xs transition-all",
            "bg-white/5 hover:bg-white/10 text-white/70 hover:text-white",
            "border border-transparent hover:border-white/20",
            transcript.status === "processing" && "border-accent-cyan/30 bg-accent-cyan/5"
          )}
        >
          <div className="flex items-start gap-2">
            <span className="text-sm flex-shrink-0 mt-0.5">{transcript.statusIcon}</span>
            <div className="flex-1 min-w-0">
              <div className="truncate font-medium">
                {transcript.command.length > 40 
                  ? transcript.command.substring(0, 40) + "..." 
                  : transcript.command}
              </div>
              <div className="text-[10px] text-white/40 mt-0.5">
                {transcript.status === "processing" ? "Running..." : transcript.status}
              </div>
            </div>
          </div>
        </motion.button>
      ))}
    </div>
  );
}

