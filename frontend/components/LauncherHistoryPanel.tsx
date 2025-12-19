"use client";

import { useRef, useEffect, useMemo, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Message, PlanState } from "@/lib/useWebSocket";
import { cn } from "@/lib/utils";
import BlueskyNotificationCard from "./BlueskyNotificationCard";
import SlashSlackSummaryCard from "./SlashSlackSummaryCard";
import TaskCompletionCard from "./TaskCompletionCard";
import FileList from "./FileList";
import DocumentList from "./DocumentList";
import StatusRow from "./StatusRow";
import logger from "@/lib/logger";
import { useGlobalEventBus } from "@/lib/telemetry";
import { spotlightUi } from "@/config/ui";
import { openExpandedWindow } from "@/lib/electron";
import { useIsElectronRuntime } from "@/hooks/useIsElectron";

interface LauncherHistoryPanelProps {
  messages: Message[];
  planState?: PlanState | null;
  isProcessing?: boolean;
  maxHeight?: number;
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

type ConversationPair = {
  id: string;
  user?: Message;
  assistant?: Message;
  statuses: Message[];
};

type HistoryItem =
  | { kind: "pair"; pair: ConversationPair }
  | { kind: "bluesky"; message: Message };

const buildHistoryItems = (messages: Message[]): HistoryItem[] => {
  const items: HistoryItem[] = [];
  let current: ConversationPair | null = null;

  const pushCurrent = () => {
    if (current && (current.user || current.assistant || current.statuses.length > 0)) {
      items.push({ kind: "pair", pair: current });
      current = null;
    }
  };

  messages.forEach((message, index) => {
    if (message.type === "bluesky_notification" && message.bluesky_notification) {
      pushCurrent();
      items.push({ kind: "bluesky", message });
      return;
    }

    if (message.type === "user" && message.message) {
      pushCurrent();
      current = {
        id: `pair-${message.timestamp || index}-${index}`,
        user: message,
        statuses: [],
      };
      return;
    }

    if (message.type === "assistant" && message.message) {
      if (!current) {
        current = {
          id: `pair-${message.timestamp || index}-${index}`,
          assistant: message,
          statuses: [],
        };
        return;
      }

      if (current.assistant) {
        pushCurrent();
        current = {
          id: `pair-${message.timestamp || index}-${index}`,
          assistant: message,
          statuses: [],
        };
        return;
      }

      current.assistant = message;
      return;
    }

    if (message.type === "status" && message.goal) {
      if (!current) {
        current = {
          id: `status-${message.timestamp || index}-${index}`,
          statuses: [message],
        };
      } else {
        current.statuses = [...current.statuses, message];
      }
    }
  });

  pushCurrent();
  return items;
};

const formatTimestampLabel = (timestamp?: string, formatter?: Intl.DateTimeFormat) => {
  if (!timestamp || !formatter) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return formatter.format(date);
};

const ConversationPairCard = memo(
  ({
    pair,
    index,
    formatter,
  }: {
    pair: ConversationPair;
    index: number;
    formatter?: Intl.DateTimeFormat;
  }) => {
    const timestampLabel = formatTimestampLabel(
      pair.assistant?.timestamp || pair.user?.timestamp,
      formatter
    );
    const assistantFileCount = pair.assistant?.files?.length ?? 0;

    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ delay: index * 0.04, duration: 0.2 }}
        className="px-4 py-3"
      >
        <div className="rounded-2xl border border-glass/25 bg-glass/20 backdrop-blur-xl p-4 shadow-inner shadow-black/10">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-white/50">
            <span className="flex items-center gap-1 text-white/60">
              <span className="text-white/50">Dialogue</span>
            </span>
            {timestampLabel && <span className="text-white/40">{timestampLabel}</span>}
          </div>

          <div className="mt-3 space-y-3">
            {pair.user && (
              <div className="flex gap-3">
                <span className="text-[10px] font-semibold text-white/50 mt-1 shrink-0">You</span>
                <div className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white/90 whitespace-pre-wrap leading-relaxed line-clamp-3">
                  {pair.user.message}
                </div>
              </div>
            )}

            {pair.assistant && (
              <div className="flex gap-3">
                <span className="text-[10px] font-semibold text-accent-primary mt-1 shrink-0">
                  Cerebros
                </span>
                <div className="flex-1 space-y-3">
                  <div className="rounded-2xl border border-accent-primary/20 bg-accent-primary/5 px-4 py-2.5 text-sm text-white/90 whitespace-pre-wrap leading-relaxed line-clamp-4">
                    {pair.assistant.message}
                  </div>
                  {pair.assistant.slash_slack && (
                    <SlashSlackSummaryCard summary={pair.assistant.slash_slack} />
                  )}
                  {pair.assistant.completion_event && (
                    <TaskCompletionCard completionEvent={pair.assistant.completion_event} />
                  )}
                  {pair.assistant.status && (
                    <StatusRow status={pair.assistant.status} />
                  )}
                  {assistantFileCount > 0 && pair.assistant.files && (
                    <FileList
                      files={pair.assistant.files}
                      summaryBlurb={pair.assistant.message}
                    />
                  )}
                  {(pair.assistant?.brainTraceUrl || pair.assistant?.brainUniverseUrl) && (
                    <div className="flex flex-wrap gap-2">
                      {pair.assistant?.brainTraceUrl && (
                        <a
                          href={pair.assistant.brainTraceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium text-white/80 hover:bg-white/10"
                        >
                          View reasoning path
                        </a>
                      )}
                      {pair.assistant?.brainUniverseUrl && (
                        <a
                          href={pair.assistant.brainUniverseUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium text-white/80 hover:bg-white/10"
                        >
                          Open Brain universe
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {pair.statuses.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {pair.statuses.map((status) => (
                <span
                  key={`${status.goal}-${status.timestamp}`}
                  className="text-[10px] text-amber-200 bg-amber-400/10 border border-amber-400/30 rounded-full px-2 py-0.5"
                >
                  🎯 {status.goal}
                </span>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    );
  }
);

ConversationPairCard.displayName = "ConversationPairCard";

export default function LauncherHistoryPanel({
  messages,
  planState,
  isProcessing,
  maxHeight = spotlightUi.historyPanel.maxHeight,
  maxTurns,
}: LauncherHistoryPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const eventBus = useGlobalEventBus();
  const isElectronRuntime = useIsElectronRuntime();
  const timeFormatter = useMemo(
    () => new Intl.DateTimeFormat(undefined, spotlightUi.historyPanel.timestampFormat),
    []
  );

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

  const {
    trimmedMessages,
    displayedTurns,
    hiddenTurns,
    displayCount,
  } = useMemo(() => {
    if (displayMessages.length === 0) {
      return {
        trimmedMessages: [],
        displayedTurns: 0,
        hiddenTurns: 0,
        displayCount: 0,
      };
    }

    const totalTurns = countUserTurns(displayMessages);
    const cutoffIndex = maxTurns ? getConversationCutoffIndex(displayMessages, maxTurns) : 0;
    const trimmed = displayMessages.slice(cutoffIndex);
    const displayed = countUserTurns(trimmed);
    return {
      trimmedMessages: trimmed,
      displayedTurns: displayed,
      hiddenTurns: Math.max(totalTurns - displayed, 0),
      displayCount: displayMessages.length,
    };
  }, [displayMessages, maxTurns]);

  const historyItems = useMemo(() => buildHistoryItems(trimmedMessages), [trimmedMessages]);
  const planIsActive = Boolean(planState && (planState.status === "planning" || planState.status === "executing"));

  if (displayCount === 0 || trimmedMessages.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-glass/30 bg-glass/10">
      <div
        ref={scrollRef}
        className="overflow-y-auto"
        style={{ maxHeight }}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 border-b border-glass/20 bg-glass/30 backdrop-blur-md">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-white/60">
            <span className="text-white/80">Recent</span>
            <span className="text-white/50">
              {maxTurns
                ? `Last ${displayedTurns} turn${displayedTurns === 1 ? "" : "s"}`
                : `${displayCount} message${displayCount === 1 ? "" : "s"}`}
            </span>
            {hiddenTurns > 0 && (
              <span className="text-[10px] text-white/40">+{hiddenTurns} older</span>
            )}
            {isProcessing && (
              <motion.span
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1.2, repeat: Infinity }}
                className="text-accent-primary text-base leading-none"
              >
                •
              </motion.span>
            )}
          </div>
        </div>

        {planIsActive && planState && (
          <div className="px-4 py-3 border-b border-glass/20 bg-glass/15">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-wide text-text-muted">Active plan</p>
                <p className="text-sm font-semibold text-text-primary truncate">{planState.goal || "Doc insights task"}</p>
                <p className="text-xs text-text-muted">
                  {planState.status === "planning" ? "Planning" : "Executing"} ·{" "}
                  {planState.steps.filter((s) => s.status === "completed").length}/{planState.steps.length} steps
                </p>
              </div>
              {isElectronRuntime && (
                <button
                  onClick={() => {
                    logger.info("[HISTORY] Expand plan summary clicked");
                    openExpandedWindow();
                  }}
                  className="shrink-0 rounded-full border border-accent-primary/40 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-accent-primary hover:bg-accent-primary/20"
                >
                  Expand
                </button>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1 text-[11px] text-text-muted">
              {planState.steps.slice(0, 5).map((step) => (
                <span
                  key={step.id}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 border",
                    step.status === "completed" && "border-green-500/40 text-green-300",
                    step.status === "running" && "border-accent-primary/40 text-accent-primary",
                    step.status === "failed" && "border-red-400/40 text-red-300",
                    step.status === "pending" && "border-white/10 text-white/60"
                  )}
                >
                  <span className="text-[10px]">
                    {step.status === "completed" ? "✓" : step.status === "running" ? "⚙️" : step.status === "failed" ? "✗" : "○"}
                  </span>
                  <span className="truncate max-w-[120px]">{step.action}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Scrollable message list */}
        <AnimatePresence mode="sync">
          {historyItems.map((item, index) => {
            if (item.kind === "pair") {
              return (
                <ConversationPairCard
                  key={item.pair.id || `pair-${index}`}
                  pair={item.pair}
                  index={index}
                  formatter={timeFormatter}
                />
              );
            }

            if (item.kind === "bluesky" && item.message.bluesky_notification) {
              return (
                <motion.div
                  key={`bluesky-${item.message.timestamp}-${index}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ delay: index * 0.04, duration: 0.2 }}
                  className="px-4 py-3"
                >
                  <BlueskyNotificationCard
                    notification={item.message.bluesky_notification}
                    onAction={(action, uri, url) => {
                      logger.info("[HISTORY] Bluesky action", { action, uri });
                      if (action === "open" && url) {
                        window.open(url, "_blank");
                      }
                    }}
                  />
                </motion.div>
              );
            }

            return null;
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Active plan indicator */}
      {planIsActive && planState && (
        <div className="px-4 py-3 border-t border-glass/20 bg-accent-primary/5 flex flex-wrap items-center justify-between gap-3">
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
          {isElectronRuntime && (
            <button
              onClick={() => {
                logger.info("[HISTORY] Expand view clicked", {
                  planStatus: planState?.status,
                  planGoal: planState?.goal,
                });
                openExpandedWindow();
              }}
              className="text-[11px] font-semibold uppercase tracking-wide text-accent-primary border border-accent-primary/40 rounded-full px-3 py-1 hover:bg-accent-primary/20 hover:text-white transition-colors"
            >
              Expand view
            </button>
          )}
        </div>
      )}
    </div>
  );
}

