"use client";

import { memo } from "react";
import { motion } from "framer-motion";
import { Message } from "@/lib/useWebSocket";
import { formatTimestamp } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface MessageBubbleProps {
  message: Message;
  index: number;
}

// Helper function to detect and render URLs as clickable links
function renderMessageWithLinks(text: string): React.ReactNode {
  // URL regex pattern - matches http/https URLs and maps:// URLs
  const urlPattern = /(https?:\/\/[^\s]+|maps:\/\/[^\s]+|https:\/\/maps\.apple\.com\/[^\s]+)/g;
  
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;
  
  while ((match = urlPattern.exec(text)) !== null) {
    // Add text before the URL
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    
    // Add clickable link
    const url = match[0];
    parts.push(
      <a
        key={match.index}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent-cyan hover:text-accent-purple underline break-all"
        onClick={(e) => {
          // For Apple Maps URLs, try to open in Maps app
          if (url.startsWith('maps://') || url.includes('maps.apple.com')) {
            e.preventDefault();
            window.open(url, '_blank');
          }
        }}
      >
        {url}
      </a>
    );
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }
  
  return parts.length > 0 ? <>{parts}</> : text;
}

const MessageBubble = memo(function MessageBubble({ message, index }: MessageBubbleProps) {
  const isUser = message.type === "user";
  const isSystem = message.type === "system";
  const isError = message.type === "error";
  const isStatus = message.type === "status";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={cn("flex w-full mb-4", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-6 py-4 backdrop-blur-xl",
          isUser && "message-user",
          !isUser && !isSystem && !isError && !isStatus && "message-assistant",
          isSystem && "message-system",
          isError && "message-error",
          isStatus && "message-assistant opacity-70"
        )}
      >
        {/* Message header */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-white/60 uppercase tracking-wider">
            {isUser && "You"}
            {!isUser && !isSystem && !isError && !isStatus && "Assistant"}
            {isSystem && "System"}
            {isError && "Error"}
            {isStatus && "Status"}
          </span>
          <span className="text-xs text-white/40">
            {formatTimestamp(message.timestamp)}
          </span>
        </div>

        {/* Message content */}
        <div className="text-white/90 leading-relaxed whitespace-pre-wrap break-words">
          {renderMessageWithLinks(message.message)}
        </div>

        {/* Status indicator */}
        {isStatus && message.status && (
          <div className="mt-3 flex items-center space-x-2">
            <div className="w-1.5 h-1.5 bg-accent-cyan rounded-full animate-pulse" />
            <span className="text-xs text-accent-cyan">{message.status}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
});

export default MessageBubble;
