"use client";

import React, { memo, useMemo, useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { Message, PlanState } from "@/lib/useWebSocket";
import { formatTimestamp } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { messageEntrance } from "@/lib/motion";
import ArtifactCard from "./ArtifactCard";
import CollapsibleMessage from "./CollapsibleMessage";
import FileList from "./FileList";
import DocumentList from "./DocumentList";
import StatusRow from "./StatusRow";
import TimelineStep from "./TimelineStep";
import SummaryCanvas from "./SummaryCanvas";
import TaskCompletionCard from "./TaskCompletionCard";
import BlueskyNotificationCard from "./BlueskyNotificationCard";
import { useToast } from "@/lib/useToast";

interface MessageBubbleProps {
  message: Message;
  index: number;
  planState?: PlanState | null;
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

const MessageBubble = memo(function MessageBubble({ message, index, planState }: MessageBubbleProps) {
  const { addToast } = useToast();
  const [isCanvasOpen, setIsCanvasOpen] = useState(false);
  const toastShownRef = useRef<Set<string>>(new Set());
  
  // DEBUG: Log files prop to verify it's received
  useEffect(() => {
    if (message.files) {
      console.log(`[MessageBubble] Message ${index} has files:`, {
        filesCount: message.files.length,
        filesType: typeof message.files,
        isArray: Array.isArray(message.files),
        firstFile: message.files[0] ? Object.keys(message.files[0]) : null,
        allFiles: message.files
      });
    } else {
      console.log(`[MessageBubble] Message ${index} has NO files prop`);
    }
  }, [message.files, index]);
  const isUser = message.type === "user";
  const isSystem = message.type === "system";
  const isError = message.type === "error";
  const isStatus = message.type === "status";
  const isPlan = message.type === "plan";
  const isBlueskyNotification = message.type === "bluesky_notification";
  const isAssistant = !isUser && !isSystem && !isError && !isStatus && !isPlan && !isBlueskyNotification;
  
  // Detect if message contains a summary (has separator pattern)
  const summaryData = useMemo(() => {
    if (!message.message || isUser || isPlan) return null;
    
    const msg = message.message;
    // Check for double newline separator (message\n\ndetails pattern)
    const separatorIndex = msg.indexOf("\n\n");
    
    if (separatorIndex > 0) {
      const messagePart = msg.substring(0, separatorIndex).trim();
      const summaryPart = msg.substring(separatorIndex + 2).trim();
      
      // Only show canvas if summary part is substantial (more than 50 chars)
      if (summaryPart.length > 50) {
        return {
          message: messagePart,
          summary: summaryPart,
        };
      }
    }
    
    // Also check for long messages that might be summaries (over 200 chars)
    if (msg.length > 200 && !msg.includes("\n\n")) {
      // Check if it looks like a summary (contains common summary keywords)
      const summaryKeywords = [
        "summary", "summarize", "overview", "in summary", "to summarize",
        "the story", "the narrator", "the main", "key points", "highlights"
      ];
      const lowerMsg = msg.toLowerCase();
      if (summaryKeywords.some(keyword => lowerMsg.includes(keyword))) {
        return {
          message: "",
          summary: msg,
        };
      }
    }
    
    return null;
  }, [message.message, isUser, isPlan]);

  // Memoize delivery status to prevent unnecessary recalculations
  const deliveryStatus = useMemo(() => {
    const messageText = message.message?.toLowerCase() || "";
    const hasEmailAction = messageText.includes("email sent") || messageText.includes("sent an email") || 
                           messageText.includes("email delivered") || messageText.match(/email.*to.*sent/i);
    const hasDownloadAction = messageText.includes("downloaded") || messageText.includes("saved to") ||
                              messageText.includes("file saved") || messageText.match(/saved.*file/i);
    const hasSendAction = messageText.includes("sent") && (messageText.includes("message") || messageText.includes("whatsapp") || messageText.includes("imessage"));
    const hasDraftAction = messageText.includes("draft") && messageText.includes("saved");

    if (hasEmailAction) {
      return { icon: "✅", text: "Email sent", variant: "success" as const };
    } else if (hasDownloadAction) {
      return { icon: "✅", text: "File saved", variant: "success" as const };
    } else if (hasSendAction) {
      return { icon: "✅", text: "Message sent", variant: "success" as const };
    } else if (hasDraftAction) {
      return { icon: "⚠", text: "Draft saved", variant: "warning" as const };
    }
    return null;
  }, [message.message]);

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
    const messageText = message.message?.toLowerCase() || "";
    const hasEmailAction = messageText.includes("email sent") || messageText.includes("sent an email") || 
                           messageText.includes("email delivered") || messageText.match(/email.*to.*sent/i);
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
  }, [message.message, isUser]);

  // Check if plan execution is complete (no more status messages after plan)
  const [isPlanExecuting, setIsPlanExecuting] = useState(isPlan);
  
  useEffect(() => {
    if (isPlan) {
      // Plan is executing until we get a final reply
      setIsPlanExecuting(true);
    }
  }, [isPlan]);

  // Trigger toast for delivery events (only if no completion_event exists)
  // Use message timestamp + content as unique key to prevent duplicate toasts
  useEffect(() => {
    if (isAssistant && deliveryStatus && !message.completion_event) {
      const messageKey = `${message.timestamp}-${message.message}`;
      
      // Only show toast if we haven't shown it for this message yet
      if (!toastShownRef.current.has(messageKey)) {
        toastShownRef.current.add(messageKey);
        addToast(
          deliveryStatus.text,
          deliveryStatus.variant === "success" ? "success" : "warning"
        );
      }
    }
  }, [isAssistant, message.timestamp, message.message, message.completion_event, deliveryStatus, addToast]);

  return (
    <motion.div
      className={cn("flex w-full mb-2 group", isUser ? "justify-end" : "justify-start")}
      initial={{ y: 12, opacity: 0, filter: "blur(12px)" }}
      animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
      transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1], delay: index * 0.03 }}
      whileHover={{ scale: 1.01 }}
    >
      <motion.div
        layout
        className={cn(
          "max-w-[80%] rounded-2xl px-5 py-4",
          isUser && "bg-gradient-to-br from-white/5 via-white/2 to-transparent shadow-[0_12px_30px_rgba(0,0,0,0.35)]",
          isAssistant && "bg-gradient-to-br from-white/5 via-white/2 to-transparent shadow-[0_12px_30px_rgba(0,0,0,0.35)]",
          isSystem && "bg-gradient-to-br from-white/3 via-white/1 to-transparent shadow-[0_12px_30px_rgba(0,0,0,0.35)]",
          isError && "bg-gradient-to-br from-red-500/5 via-red-500/2 to-transparent shadow-[0_12px_30px_rgba(0,0,0,0.35)]",
          isStatus && "bg-gradient-to-br from-white/3 via-white/1 to-transparent shadow-[0_12px_30px_rgba(0,0,0,0.35)]",
          isPlan && "bg-gradient-to-br from-white/5 via-white/2 to-transparent shadow-[0_12px_30px_rgba(0,0,0,0.35)]",
          isBlueskyNotification && "bg-gradient-to-br from-blue-500/5 via-blue-500/2 to-transparent shadow-[0_12px_30px_rgba(0,0,0,0.35)]"
        )}
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.25, ease: "easeOut", delay: index * 0.05 }}
      >
        {/* Message header */}
        <div className="flex items-center justify-between mb-3 relative">
          <span className={cn(
            "text-sm font-semibold uppercase tracking-wide",
            isAssistant && "text-text-primary",
            isUser && "text-text-primary",
            isSystem && "text-text-muted",
            isError && "text-accent-danger",
            isStatus && "text-text-muted",
            isPlan && "text-text-primary",
            isBlueskyNotification && "text-blue-400"
          )}>
            {isUser && "You"}
            {isAssistant && "Cerebro"}
            {isSystem && "System"}
            {isError && "Error"}
            {isStatus && "Status"}
            {isPlan && "Plan"}
            {isBlueskyNotification && "Bluesky"}
          </span>
          <motion.span
            className="text-xs font-medium text-white/35"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, ease: "easeOut", delay: (index * 0.03) + 0.2 }}
          >
            {formatTimestamp(message.timestamp)}
          </motion.span>
        </div>

        {/* Plan content - show task breakdown */}
        {isPlan && (message.steps && message.steps.length > 0 || planState) && (
          <TimelineStep
            steps={message.steps}
            goal={message.goal}
            activeStepIndex={isPlanExecuting ? 0 : undefined}
            planState={planState}
          />
        )}

        {/* Message content */}
        {!isPlan && (
          <div>
            <CollapsibleMessage
              content={message.message}
              className={cn(
                "leading-[1.5] text-[15px]",
                isAssistant && "text-text-primary font-medium",
                isUser && "text-text-primary font-medium",
                isSystem && "text-text-primary font-medium",
                isError && "text-accent-danger font-medium"
              )}
            >
              {renderMessageWithLinks(message.message || "", isUser)}
            </CollapsibleMessage>
            
            {/* Summary Canvas Button */}
            {summaryData && isAssistant && (
              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={() => setIsCanvasOpen(true)}
                  className={cn(
                    "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg",
                    "text-sm font-medium transition-colors",
                    "bg-accent-primary/10 hover:bg-accent-primary/20",
                    "text-accent-primary border border-accent-primary/20",
                    "hover:border-accent-primary/40"
                  )}
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <span>View Summary</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Task Completion Card - Rich feedback for completed actions */}
        {isAssistant && message.completion_event && (
          <TaskCompletionCard
            completionEvent={message.completion_event}
          />
        )}

        {/* Bluesky Notification Card - Interactive notification display */}
        {(isSystem || isAssistant) && message.type === "bluesky_notification" && message.bluesky_notification && (
          <BlueskyNotificationCard
            notification={message.bluesky_notification}
            onAction={(action, uri, url) => {
              if (action === "open" && url) {
                // Open the post in browser using the correct URL
                window.open(url, '_blank');
              } else if (action === "reply" && uri) {
                // Send reply command to chat input
                const command = `/bluesky reply "${uri}" ""`;
                // We need to access the chat input somehow - this would need a prop or context
                // For now, we'll dispatch a custom event that the chat interface can listen to
                window.dispatchEvent(new CustomEvent('bluesky-action', {
                  detail: { action: 'prefill-input', command }
                }));
              } else if ((action === "like" || action === "repost") && uri) {
                // Send like/repost command directly
                const command = `/bluesky ${action} ${uri}`;
                window.dispatchEvent(new CustomEvent('bluesky-action', {
                  detail: { action: 'send-command', command }
                }));
              }
            }}
          />
        )}

        {/* Status indicator */}
        {isStatus && message.status && (
          <StatusRow status={message.status} className="mt-2" />
        )}

        {/* Inline delivery feedback - fallback for messages without completion_event */}
        {isAssistant && deliveryStatus && !message.completion_event && (
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

        {/* File list (consolidated - handles both list_related_documents and search results) */}
        {isAssistant && message.files && Array.isArray(message.files) && message.files.length > 0 && (
          <FileList
            files={message.files}
            summaryBlurb={message.message}
            totalCount={undefined} // Could be extracted from raw result if needed
          />
        )}

        {/* Document list (separate from files array) */}
        {isAssistant && message.documents && Array.isArray(message.documents) && message.documents.length > 0 && (
          <DocumentList
            documents={message.documents}
            summaryMessage={message.message}
            totalCount={undefined}
          />
        )}

        {/* Artifact cards (only show if no file list or document list) */}
        {isAssistant && artifacts.length > 0 && !message.files && !message.documents && (
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
      </motion.div>

      {/* Summary Canvas */}
      {summaryData && (
        <SummaryCanvas
          isOpen={isCanvasOpen}
          onClose={() => setIsCanvasOpen(false)}
          title={(() => {
            // Try to extract a meaningful title from the message
            const msg = summaryData.message || message.message || "";
            // Look for document/book titles or author names
            const titlePatterns = [
              /(?:summary|summarize|summary of)\s+(?:the\s+)?["']?([^"']+)["']?/i,
              /(?:book|document|story|work)\s+(?:by|from)\s+([^,\.]+)/i,
              /["']([^"']+)["']?\s+(?:by|from)\s+([^,\.]+)/i,
            ];
            
            for (const pattern of titlePatterns) {
              const match = msg.match(pattern);
              if (match && match[1]) {
                return `${match[1].trim()} Summary`;
              }
            }
            
            // Fallback: use first few words of message if it's short
            if (msg.length > 0 && msg.length < 50) {
              return msg;
            }
            
            return "Document Summary";
          })()}
          summary={summaryData.summary}
          message={summaryData.message}
        />
      )}
    </motion.div>
  );
});

export default MessageBubble;
