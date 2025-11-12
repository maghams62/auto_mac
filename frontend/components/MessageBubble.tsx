"use client";

import React, { memo, useMemo, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Message } from "@/lib/useWebSocket";
import { formatTimestamp } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { messageEntrance } from "@/lib/motion";
import ArtifactCard from "./ArtifactCard";
import CollapsibleMessage from "./CollapsibleMessage";
import FileList from "./FileList";
import StatusRow from "./StatusRow";
import TimelineStep from "./TimelineStep";
import { useToast } from "@/lib/useToast";

interface MessageBubbleProps {
  message: Message;
  index: number;
}

// Helper function to detect and render URLs as clickable links
function renderMessageWithLinks(text: string, isUser: boolean): React.ReactNode {
  // URL regex pattern - matches http/https URLs and maps:// URLs
  const urlPattern = /(https?:\/\/[^\s]+|maps:\/\/[^\s]+|https:\/\/maps\.apple\.com\/[^\s]+)/g;
  
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;
  
  while ((match = urlPattern.exec(text)) !== null) {
    // Add text before the URL
    if (match.index > lastIndex) {
      const beforeText = text.substring(lastIndex, match.index);
      if (isUser) {
        parts.push(
          <span key={`text-${match.index}`} className="font-mono text-sm">
            {beforeText}
          </span>
        );
      } else {
        parts.push(beforeText);
      }
    }
    
    // Add clickable link
    const url = match[0];
    parts.push(
      <a
        key={match.index}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent-primary hover:opacity-80 underline break-all"
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
    const remainingText = text.substring(lastIndex);
    if (isUser) {
      parts.push(
        <span key={`text-end`} className="font-mono text-sm">
          {remainingText}
        </span>
      );
    } else {
      parts.push(remainingText);
    }
  }
  
  return parts.length > 0 ? <>{parts}</> : (isUser ? <span className="font-mono text-sm">{text}</span> : text);
}

const MessageBubble = memo(function MessageBubble({ message, index }: MessageBubbleProps) {
  const { addToast } = useToast();
  const isUser = message.type === "user";
  const isSystem = message.type === "system";
  const isError = message.type === "error";
  const isStatus = message.type === "status";
  const isPlan = message.type === "plan";
  const isAssistant = !isUser && !isSystem && !isError && !isStatus && !isPlan;

  // Detect delivery actions from message content
  const messageText = message.message?.toLowerCase() || "";
  const hasEmailAction = messageText.includes("email sent") || messageText.includes("sent an email") || 
                         messageText.includes("email delivered") || messageText.match(/email.*to.*sent/i);
  const hasDownloadAction = messageText.includes("downloaded") || messageText.includes("saved to") ||
                            messageText.includes("file saved") || messageText.match(/saved.*file/i);
  const hasSendAction = messageText.includes("sent") && (messageText.includes("message") || messageText.includes("whatsapp") || messageText.includes("imessage"));
  const hasDraftAction = messageText.includes("draft") && messageText.includes("saved");

  // Determine delivery status
  let deliveryStatus: { icon: string; text: string; variant: "success" | "warning" } | null = null;
  if (hasEmailAction) {
    deliveryStatus = { icon: "✅", text: "Email sent", variant: "success" };
  } else if (hasDownloadAction) {
    deliveryStatus = { icon: "✅", text: "File saved", variant: "success" };
  } else if (hasSendAction) {
    deliveryStatus = { icon: "✅", text: "Message sent", variant: "success" };
  } else if (hasDraftAction) {
    deliveryStatus = { icon: "⚠", text: "Draft saved", variant: "warning" };
  }

  // Extract artifacts (file paths, email addresses, URLs) from message
  const artifacts = useMemo(() => {
    if (!message.message || isUser) return [];
    
    const found: Array<{ path: string; type: "file" | "email" | "url"; size?: string }> = [];
    
    // Match file paths (absolute paths starting with / or relative paths with extensions)
    const filePathPattern = /(?:^|\s)(\/[^\s]+|\.\/[^\s]+|[^\s]+\/[^\s]+\.(pdf|docx?|txt|md|html|zip|png|jpg|jpeg|gif|svg|key|pages|numbers|ppt|pptx|xls|xlsx|csv|json|xml|yaml|yml))/gi;
    const fileMatches = Array.from(message.message.matchAll(filePathPattern));
    for (const match of fileMatches) {
      const path = match[1]?.trim();
      if (path && path.length > 3 && path.length < 500) {
        found.push({ path, type: "file" });
      }
    }
    
    // Match email addresses (for email confirmations)
    if (hasEmailAction) {
      const emailPattern = /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
      const emailMatches = Array.from(message.message.matchAll(emailPattern));
      for (const match of emailMatches) {
        const email = match[1];
        if (email && !found.some(a => a.path === email)) {
          found.push({ path: email, type: "email" });
        }
      }
    }
    
    // Remove duplicates
    const unique = Array.from(new Map(found.map(a => [a.path, a])).values());
    return unique.slice(0, 5); // Limit to 5 artifacts
  }, [message.message, isUser, hasEmailAction]);

  // Check if plan execution is complete (no more status messages after plan)
  const [isPlanExecuting, setIsPlanExecuting] = useState(isPlan);
  
  useEffect(() => {
    if (isPlan) {
      // Plan is executing until we get a final reply
      setIsPlanExecuting(true);
    }
  }, [isPlan]);

  // Trigger toast for delivery events
  useEffect(() => {
    if (isAssistant && deliveryStatus) {
      addToast(
        deliveryStatus.text,
        deliveryStatus.variant === "success" ? "success" : "warning"
      );
    }
  }, [isAssistant, deliveryStatus, addToast]);

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={messageEntrance}
      className={cn("flex w-full mb-4 group", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-5 py-3 backdrop-blur-glass shadow-inset-border",
          isUser && "bg-glass-user",
          isAssistant && "bg-glass-assistant",
          isSystem && "bg-glass-assistant",
          isError && "bg-glass-assistant border border-danger-border",
          isStatus && "bg-glass-assistant opacity-75",
          isPlan && "bg-glass-assistant"
        )}
      >
        {/* Message header */}
        <div className="flex items-center justify-between mb-2 relative">
          <span className={cn(
            "text-xs font-medium uppercase tracking-wider",
            isAssistant && "text-text-muted font-medium",
            isUser && "text-text-muted font-medium",
            isSystem && "text-text-muted",
            isError && "text-accent-danger",
            isStatus && "text-text-muted",
            isPlan && "text-text-muted"
          )}>
            {isUser && "You"}
            {isAssistant && "Assistant"}
            {isSystem && "System"}
            {isError && "Error"}
            {isStatus && "Status"}
            {isPlan && "Plan"}
          </span>
          <span className="text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-150" style={{ color: "rgba(255, 255, 255, 0.45)", fontSize: "12px" }}>
            {formatTimestamp(message.timestamp)}
          </span>
        </div>

        {/* Plan content - show task breakdown */}
        {isPlan && message.steps && message.steps.length > 0 && (
          <TimelineStep
            steps={message.steps}
            goal={message.goal}
            activeStepIndex={isPlanExecuting ? 0 : undefined}
          />
        )}

        {/* Message content */}
        {!isPlan && (
          <CollapsibleMessage
            content={message.message}
            className={cn(
              "leading-[1.4]",
              isAssistant && "text-text-primary font-medium",
              isUser && "text-text-primary",
              isSystem && "text-text-primary",
              isError && "text-accent-danger"
            )}
          >
            {renderMessageWithLinks(message.message || "", isUser)}
          </CollapsibleMessage>
        )}

        {/* Status indicator */}
        {isStatus && message.status && (
          <StatusRow status={message.status} className="mt-2" />
        )}

        {/* Inline delivery feedback */}
        {isAssistant && deliveryStatus && (
          <div className={cn(
            "mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium",
            deliveryStatus.variant === "success" 
              ? "bg-success-bg text-accent-success border border-success-border"
              : "bg-warning-bg text-accent-warning border border-warning-border"
          )}>
            <span>{deliveryStatus.icon}</span>
            <span>{deliveryStatus.text}</span>
          </div>
        )}

        {/* File list (for list_related_documents results) */}
        {isAssistant && message.files && message.files.length > 0 && (
          <FileList
            files={message.files}
            summaryBlurb={undefined} // Could be extracted from message if needed
            totalCount={undefined} // Could be extracted from message if needed
          />
        )}

        {/* Artifact cards (only show if no file list) */}
        {isAssistant && artifacts.length > 0 && !message.files && (
          <div className="mt-3 space-y-2">
            {artifacts.map((artifact, idx) => (
              <ArtifactCard
                key={`${artifact.path}-${idx}`}
                path={artifact.path}
                type={artifact.type}
                size={artifact.size}
              />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
});

export default MessageBubble;
