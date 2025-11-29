"use client";

import { useRef, useEffect, useCallback, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Message, PlanState } from "@/lib/useWebSocket";
import { cn } from "@/lib/utils";
import BlueskyNotificationCard from "./BlueskyNotificationCard";
import logger from "@/lib/logger";
import { useGlobalEventBus } from "@/lib/telemetry";

interface LauncherHistoryPanelProps {
  messages: Message[];
  planState?: PlanState | null;
  isProcessing?: boolean;
  maxHeight?: number;
  onExpand?: () => void;
  maxTurns?: number;
}

const countUserTurns = (messages: Message[]) =>
  messages.reduce((count, msg) => (msg.type === "user" && msg.message ? count + 1 : count), 0);

const getConversationCutoffIndex = (messages: Message[], turns: number) => {
  if (!turns || turns <= 0) return 0;
  let remaining = turns;

  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message.type === "user" && message.message) {
      remaining -= 1;
      if (remaining === 0) {
        return i;
      }
    }
  }

  return 0;
};

// Compact message component for launcher history
const CompactMessage = memo(({ message, index }: { message: Message; index: number }) => {
  const isUser = message.type === "user";
  const isAssistant = message.type === "assistant";
  const isStatus = message.type === "status";
  const isBluesky = message.type === "bluesky_notification";

  // Skip status messages in compact view
  if (isStatus && message.status === "processing") return null;

  // Bluesky notification
  if (isBluesky && message.bluesky_notification) {
    return (
      <div className="px-3 py-2">
        <BlueskyNotificationCard
          notification={message.bluesky_notification}
          onAction={(action, uri, url) => {
            logger.info("[HISTORY] Bluesky action", { action, uri });
            if (action === "open" && url) {
              window.open(url, "_blank");
            }
          }}
        />
      </div>
    );
  }

  // User message
  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, x: 10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.05 }}
        className="flex justify-end px-3 py-1.5"
      >
        <div className="max-w-[80%] bg-accent-primary/20 text-text-primary rounded-xl px-3 py-2 text-sm">
          {message.message}
        </div>
      </motion.div>
    );
  }

  // Assistant message
  if (isAssistant && message.message) {
    return (
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.05 }}
        className="flex justify-start px-3 py-1.5"
      >
        <div className="max-w-[85%] bg-glass/30 text-text-primary rounded-xl px-3 py-2 text-sm">
          <div className="whitespace-pre-wrap leading-relaxed line-clamp-4">
            {message.message}
          </div>
          {/* Show file count if present */}
          {message.files && message.files.length > 0 && (
            <div className="mt-1.5 text-xs text-text-muted flex items-center gap-1">
              <span>📁</span>
              <span>{message.files.length} file{message.files.length > 1 ? 's' : ''}</span>
            </div>
          )}
        </div>
      </motion.div>
    );
  }

  // Status with goal (plan started)
  if (isStatus && message.goal) {
    return (
      <div className="px-3 py-1.5">
        <div className="text-xs text-accent-primary flex items-center gap-1.5">
          <span>🎯</span>
          <span className="truncate">{message.goal}</span>
        </div>
      </div>
    );
  }

  return null;
});

CompactMessage.displayName = "CompactMessage";

export default function LauncherHistoryPanel({
  messages,
  planState,
  isProcessing,
  maxHeight = 200,
  onExpand,
  maxTurns,
}: LauncherHistoryPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const eventBus = useGlobalEventBus();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Handle keyboard shortcuts for scrolling
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!scrollRef.current) return;

      if (e.key === "PageUp") {
        e.preventDefault();
        scrollRef.current.scrollBy({ top: -100, behavior: "smooth" });
        logger.debug("[HISTORY] PageUp scroll");
        eventBus.emit('history:scroll', { direction: 'up', source: 'keyboard' });
      } else if (e.key === "PageDown") {
        e.preventDefault();
        scrollRef.current.scrollBy({ top: 100, behavior: "smooth" });
        logger.debug("[HISTORY] PageDown scroll");
        eventBus.emit('history:scroll', { direction: 'down', source: 'keyboard' });
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [eventBus]);

  // Filter messages for display (skip empty/internal ones)
  const displayMessages = messages.filter(msg => {
    if (msg.type === "user" && msg.message) return true;
    if (msg.type === "assistant" && msg.message) return true;
    if (msg.type === "bluesky_notification" && msg.bluesky_notification) return true;
    if (msg.type === "status" && msg.goal) return true;
    return false;
  });

  // Don't show if no messages
  if (displayMessages.length === 0) return null;

  const totalTurns = countUserTurns(displayMessages);
  const cutoffIndex = maxTurns ? getConversationCutoffIndex(displayMessages, maxTurns) : 0;
  const trimmedMessages = displayMessages.slice(cutoffIndex);
  const displayedTurns = countUserTurns(trimmedMessages);
  const hiddenTurns = Math.max(totalTurns - displayedTurns, 0);

  return (
    <div className="border-t border-glass/30 bg-glass/10">
      {/* Header with expand button */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-glass/20">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span>💬</span>
          <span>
            {maxTurns
              ? `Conversation (Last ${displayedTurns} turn${displayedTurns === 1 ? "" : "s"})`
              : `Conversation (${displayMessages.length})`}
          </span>
          {hiddenTurns > 0 && (
            <span className="text-[10px] uppercase tracking-wide text-text-muted/70">
              +{hiddenTurns} older
            </span>
          )}
          {isProcessing && (
            <motion.span
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1.5, repeat: Infinity }}
              className="text-accent-primary"
            >
              •
            </motion.span>
          )}
        </div>
        {onExpand && (
          <button
            onClick={() => {
              logger.info("[HISTORY] Expand button clicked");
              eventBus.emit('window:expand', { 
                messageCount: displayMessages.length,
                timestamp: Date.now() 
              });
              onExpand();
            }}
            className="text-xs text-text-muted hover:text-text-primary transition-colors flex items-center gap-1 px-2 py-0.5 rounded hover:bg-glass-hover"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
            <span>Expand</span>
          </button>
        )}
      </div>

      {/* Scrollable message list */}
      <div
        ref={scrollRef}
        className="overflow-y-auto"
        style={{ maxHeight }}
      >
        <AnimatePresence mode="popLayout">
          {trimmedMessages.map((message, index) => (
            <CompactMessage key={`${message.type}-${index}`} message={message} index={index} />
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Active plan indicator */}
      {planState && (planState.status === "executing" || planState.status === "planning") && (
        <div className="px-3 py-2 border-t border-glass/20 bg-accent-primary/5">
          <div className="flex items-center gap-2 text-xs">
            <motion.span
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            >
              ⚙️
            </motion.span>
            <span className="text-accent-primary font-medium">
              {planState.status === "planning" ? "Planning..." : "Executing..."}
            </span>
            {planState.steps.length > 0 && (
              <span className="text-text-muted">
                {planState.steps.filter(s => s.status === "completed").length}/{planState.steps.length} steps
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

