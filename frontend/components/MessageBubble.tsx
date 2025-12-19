"use client";

import React, { memo, useMemo, useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { Message, PlanState, EvidenceItem, SlackSourceItem, DocPriority, IncidentCandidate } from "@/lib/useWebSocket";
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
import ApidocsDriftCard from "./ApidocsDriftCard";
import { useToast } from "@/lib/useToast";
import { getApiBaseUrl } from "@/lib/apiConfig";
import SlashSlackSummaryCard from "./SlashSlackSummaryCard";
import SlashGitSummaryCard from "./SlashGitSummaryCard";
import SlashCerebrosSummaryCard from "./SlashCerebrosSummaryCard";
import YouTubeSummaryCard from "./YouTubeSummaryCard";
import { CreateDocIssueModal } from "./CreateDocIssueModal";
import { buildDashboardComponentUrl } from "@/lib/dashboardLinks";
import { openExternalUrl, copyToClipboard } from "@/lib/externalLinks";
import { IncidentCTA } from "./IncidentCTA";

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
  const [showDocIssueModal, setShowDocIssueModal] = useState(false);
  const [showExplainability, setShowExplainability] = useState(false);
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
  const isApidocsDrift = message.type === "apidocs_drift";
  const isAssistant = !isUser && !isSystem && !isError && !isStatus && !isPlan && !isBlueskyNotification && !isApidocsDrift;
  const evidenceEntries = message.evidence ?? [];
  const dashboardUrl = buildDashboardComponentUrl(message.componentIds?.[0]);
  const explainAvailable =
    isAssistant &&
    ((message.evidence && message.evidence.length > 0) || (message.toolRuns && message.toolRuns.length > 0));
  const canFileDocIssue = Boolean(message.investigationId && message.componentIds?.length && evidenceEntries.length);
  const hasDashboardComponent = Boolean(message.componentIds?.length);
  
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

  const isYouTubeMessage = isAssistant && (message.command === "youtube" || message.agent === "youtube" || Boolean(message.youtube));
  const cerebrosAnswer = message.cerebrosAnswer;
  const cerebrosOptionLabel = useMemo(() => {
    const option = cerebrosAnswer?.option;
    if (option === "activity_graph") {
      return "Option 1 · documentation health";
    }
    if (option === "cross_system_context") {
      return "Option 2 · cross-system impact";
    }
    return null;
  }, [cerebrosAnswer?.option]);
  const docPriorities = cerebrosAnswer?.doc_priorities;

  const youtubeDetails = useMemo(() => {
    if (!isYouTubeMessage || !message.details) {
      return null;
    }
    const lines = message.details
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) {
      return null;
    }
    let metaLine: string | null = null;
    const references: Array<{ timestamp?: string; text: string }> = [];
    for (const line of lines) {
      if (line.startsWith("-")) {
        const match = line.match(/-\s*\(~([^)]*)\)\s*(.+)/);
        if (match) {
          references.push({ timestamp: match[1], text: match[2].trim() });
        } else {
          references.push({ text: line.replace(/^-+\s*/, "").trim() });
        }
      } else if (!metaLine) {
        metaLine = line;
      } else {
        references.push({ text: line });
      }
    }
    return { metaLine, references };
  }, [isYouTubeMessage, message.details]);

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

  const normalizedStatus = (message.status || "").toLowerCase();
  const hasStatusMessage = Boolean(message.message && message.message.trim().length > 0);
  const isSkippableStatus =
    isStatus &&
    !hasStatusMessage &&
    (normalizedStatus === "complete" || normalizedStatus === "idle");
  const shouldShowStatusChip =
    isStatus && Boolean(message.status) && ["processing", "thinking", "cancelling"].includes(normalizedStatus);

  if (isSkippableStatus) {
    return null;
  }

  const bubble = (
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

            {isAssistant && cerebrosOptionLabel && !message.slash_cerebros ? (
              <div className="mt-3 inline-flex items-center rounded-full border border-white/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white/70">
                {cerebrosOptionLabel}
              </div>
            ) : null}

            {isAssistant && !message.slash_cerebros && docPriorities && docPriorities.length > 0 ? (
              <DocPriorityList priorities={docPriorities} />
            ) : null}

            {isYouTubeMessage && message.youtube && (
              <div className="mt-4">
                <YouTubeSummaryCard payload={message.youtube} />
              </div>
            )}
            {isYouTubeMessage && !message.youtube && (
              <div className="mt-3 space-y-2 text-sm text-slate-200">
                {youtubeDetails?.metaLine && <p className="text-xs uppercase tracking-wide text-slate-400">{youtubeDetails.metaLine}</p>}
                {youtubeDetails?.references?.length ? (
                  <ul className="space-y-1">
                    {youtubeDetails.references.map((reference, index) => (
                      <li key={`${reference.text}-${index}`} className="flex items-start gap-2 text-slate-200">
                        {reference.timestamp && <span className="font-mono text-[11px] text-cyan-300">{reference.timestamp}</span>}
                        <span className="flex-1 text-xs text-slate-300">{reference.text}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            )}
            
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

        {/* Slack quick link tile */}
        {isAssistant && message.slash_slack?.sources?.length ? (
          <SlackQuickLinkTile sources={message.slash_slack.sources} addToast={addToast} />
        ) : null}

        {isAssistant && !message.slash_cerebros && message.incidentCandidate ? (
          <>
            <IncidentStructuredSummary candidate={message.incidentCandidate} />
            <IncidentCTA
              candidate={message.incidentCandidate}
              incidentId={message.incidentId}
              investigationId={message.investigationId}
              className="mt-4"
            />
          </>
        ) : null}

        {/* Task Completion Card - Rich feedback for completed actions */}
        {isAssistant && message.slash_slack && (
          <SlashSlackSummaryCard summary={message.slash_slack} queryPlan={message.queryPlan} />
        )}

        {isAssistant && message.slash_git && (
          <SlashGitSummaryCard summary={message.slash_git} queryPlan={message.queryPlan} />
        )}

        {isAssistant && message.slash_cerebros && (
          <SlashCerebrosSummaryCard
            summary={message.slash_cerebros}
            queryPlan={message.queryPlan}
            hideAnswerText={Boolean(message.message)}
          />
        )}

        {/* Task Completion Card - Rich feedback for completed actions */}
        {isAssistant && message.completion_event && (
          <TaskCompletionCard
            completionEvent={message.completion_event}
          />
        )}

        {isAssistant && (message.brainTraceUrl || message.brainUniverseUrl) && (
          <div className="mt-4 flex flex-wrap gap-3">
            {message.brainTraceUrl && (
              <a
                href={message.brainTraceUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-white/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-white/90 transition hover:border-white/40 hover:text-white"
              >
                View reasoning path
                <span aria-hidden="true">↗</span>
              </a>
            )}
            {message.brainUniverseUrl && (
              <a
                href={message.brainUniverseUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-white/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-white/90 transition hover:border-white/40 hover:text-white"
              >
                Open in Brain Universe
                <span aria-hidden="true">↗</span>
              </a>
            )}
          </div>
        )}

        {isAssistant && explainAvailable ? (
          <div className="mt-4 space-y-2">
            <button
              className="rounded-full border border-white/20 px-3 py-1.5 text-xs font-semibold text-white/80 transition hover:border-white/40 hover:text-white"
              onClick={() => setShowExplainability((prev) => !prev)}
            >
              {showExplainability ? "Hide why this answer" : "Why this answer?"}
            </button>
            {showExplainability ? (
              <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-3">
                <EvidenceList evidence={message.evidence} />
                <ToolRunList toolRuns={message.toolRuns} />
              </div>
            ) : null}
          </div>
        ) : null}

        {isAssistant && (canFileDocIssue || hasDashboardComponent) ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {canFileDocIssue ? (
              <button
                className="rounded-xl border border-white/20 px-3 py-1.5 text-xs font-semibold text-white/80 transition hover:border-white/40 hover:text-white"
                onClick={() => setShowDocIssueModal(true)}
              >
                Create doc issue
              </button>
            ) : null}
            {dashboardUrl ? (
              <a
                href={dashboardUrl}
                target="_blank"
                rel="noreferrer"
                className="rounded-xl border border-white/20 px-3 py-1.5 text-xs font-semibold text-white/80 transition hover:border-white/40 hover:text-white"
              >
                Open dashboard
              </a>
            ) : hasDashboardComponent ? (
              <button
                className="rounded-xl border border-white/20 px-3 py-1.5 text-xs font-semibold text-white/80 transition hover:border-white/40 hover:text-white"
                onClick={() =>
                  addToast("Dashboard base URL is not configured; set NEXT_PUBLIC_DASHBOARD_BASE_URL to enable deep links.", "warning")
                }
              >
                Dashboard link unavailable
              </button>
            ) : null}
          </div>
        ) : null}

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

        {/* API Docs Drift Card - Self-evolving documentation (Oqoqo pattern) */}
        {isApidocsDrift && message.apidocs_drift && (
          <ApidocsDriftCard
            driftReport={message.apidocs_drift}
            onApprove={async (proposedSpec) => {
              // Call the apply endpoint
              const apiBase = getApiBaseUrl();
              const response = await fetch(`${apiBase}/api/apidocs/apply`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  proposed_spec: proposedSpec,
                  create_backup: true,
                }),
              });
              if (!response.ok) {
                throw new Error("Failed to apply spec update");
              }
            }}
            onDismiss={() => {
              // Could dispatch event to remove from chat or mark as dismissed
              console.log("API docs drift dismissed");
            }}
            onViewDocs={() => {
              // Open Swagger UI
              window.open("http://localhost:8000/docs", "_blank");
            }}
          />
        )}

        {/* Status indicator */}
        {shouldShowStatusChip && message.status && (
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
    </motion.div>
  );

  return (
    <>
      {bubble}

      {canFileDocIssue ? (
        <CreateDocIssueModal
          isOpen={showDocIssueModal}
          onClose={() => setShowDocIssueModal(false)}
          investigationId={message.investigationId}
          componentIds={message.componentIds}
          evidence={evidenceEntries}
          defaultSummary={message.message}
        />
      ) : null}

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
    </>
  );
});

export default MessageBubble;

const INCIDENT_SIGNAL_DESCRIPTORS: Record<
  string,
  {
    label: string;
    prefix: string;
  }
> = {
  git_events: { label: "Git", prefix: "🔥" },
  git_items: { label: "Git", prefix: "🔥" },
  slack_threads: { label: "Slack threads", prefix: "💬" },
  slack_conversations: { label: "Slack", prefix: "💬" },
  slack_complaints: { label: "Complaints", prefix: "😡" },
  support_complaints: { label: "Support", prefix: "😡" },
  doc_issues: { label: "Doc issues", prefix: "📄" },
  issues: { label: "Tickets", prefix: "📨" },
};

const IncidentStructuredSummary = ({ candidate }: { candidate: IncidentCandidate }) => {
  const resolutionPlan = normalizeIncidentPlan(candidate.resolution_plan);
  const scopeSummary = [
    candidate.counts?.components ? `${candidate.counts.components} components` : null,
    candidate.counts?.docs ? `${candidate.counts.docs} docs` : null,
    candidate.counts?.issues ? `${candidate.counts.issues} tickets` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const hasSignals = Boolean(
    (candidate.activity_signals && Object.keys(candidate.activity_signals).length) ||
      (candidate.dissatisfaction_signals && Object.keys(candidate.dissatisfaction_signals).length),
  );

  return (
    <div
      className="mt-4 space-y-3 rounded-2xl border border-white/15 bg-white/5 p-4 shadow-inner shadow-black/20"
      data-testid="incident-structured-summary"
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-white/60">Incident preview</p>
          {candidate.impact_summary ? (
            <p className="text-sm text-white/80">{candidate.impact_summary}</p>
          ) : scopeSummary ? (
            <p className="text-sm text-white/70">{scopeSummary}</p>
          ) : null}
        </div>
        <div className="inline-flex items-center rounded-full border border-white/20 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white/80">
          {candidate.severity} · {Math.round(candidate.blast_radius_score ?? 0)}
        </div>
      </div>
      {candidate.root_cause_explanation ? (
        <p className="text-sm text-white/90">{candidate.root_cause_explanation}</p>
      ) : null}
      {candidate.recency_info?.hours_since !== undefined ? (
        <p className="text-[11px] uppercase tracking-wide text-white/40">
          Last signal {candidate.recency_info.hours_since}h ago
        </p>
      ) : null}
      {resolutionPlan?.length ? (
        <div>
          <p className="text-[11px] uppercase tracking-wide text-white/50">Next steps</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-white/80">
            {resolutionPlan.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {hasSignals ? (
        <div className="flex flex-wrap gap-2">
          {renderIncidentSignalChips(candidate.activity_signals, "activity")}
          {renderIncidentSignalChips(candidate.dissatisfaction_signals, "dissatisfaction")}
        </div>
      ) : null}
    </div>
  );
};

function normalizeIncidentPlan(value: IncidentCandidate["resolution_plan"]): string[] | undefined {
  if (!value) return undefined;
  if (Array.isArray(value)) {
    const normalized = value.map((entry) => entry?.trim()).filter(Boolean) as string[];
    return normalized.length ? normalized : undefined;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : undefined;
  }
  return undefined;
}

function renderIncidentSignalChips(
  signals?: Record<string, number>,
  variant: "activity" | "dissatisfaction" = "activity",
) {
  if (!signals) return null;
  return Object.entries(signals)
    .filter(([, value]) => typeof value === "number" && value > 0)
    .map(([key, value]) => {
      const descriptor = INCIDENT_SIGNAL_DESCRIPTORS[key] || {
        label: key.replace(/_/g, " "),
        prefix: variant === "activity" ? "🔥" : "😡",
      };
      return (
        <span
          key={`${variant}-${key}`}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
            variant === "activity" ? "border-emerald-400/40 text-emerald-50" : "border-rose-400/40 text-rose-100",
          )}
        >
          {descriptor.prefix} {descriptor.label} <span className="font-bold">{value}</span>
        </span>
      );
    });
}

const DocPriorityList = ({ priorities }: { priorities: DocPriority[] }) => {
  if (!priorities?.length) {
    return null;
  }

  const entries = priorities.slice(0, 3);

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-white/60">Top docs to update</h4>
      <div className="mt-2 space-y-2">
        {entries.map((priority, index) => {
          const title = priority.doc_title || priority.doc_id || `Document ${index + 1}`;
          return (
            <div key={`${priority.doc_id || title}-${index}`} className="rounded-xl border border-white/10 bg-black/20 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                {priority.doc_url ? (
                  <a href={priority.doc_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-white hover:underline">
                    {title}
                  </a>
                ) : (
                  <span className="text-sm font-semibold text-white">{title}</span>
                )}
                <div className="flex items-center gap-2">
                  {priority.severity ? (
                    <span className="rounded-full border border-white/20 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/70">
                      {priority.severity}
                    </span>
                  ) : null}
                  <span className="text-xs font-semibold text-white/70">{priority.score.toFixed(2)}</span>
                </div>
              </div>
              {priority.reason ? (
                <p className="mt-1 text-xs text-white/70">{priority.reason}</p>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const SlackQuickLinkTile = ({
  sources,
  addToast,
}: {
  sources: SlackSourceItem[];
  addToast: (message: string, variant?: "success" | "warning" | "error") => void;
}) => {
  if (!sources?.length) {
    return null;
  }
  const primary = sources.find((source) => source.permalink) ?? sources[0];
  if (!primary) {
    return null;
  }

  const timestampLabel = formatSlackSourceTimestamp(primary.iso_time, primary.ts);
  const channelLabel = primary.channel || "#slack";

  const handleOpen = async () => {
    const targetUrl = primary.deep_link || primary.permalink;
    if (!targetUrl) {
      addToast("Slack link unavailable for this source.", "warning");
      return;
    }
    const opened = openExternalUrl(targetUrl);
    if (!opened && primary.permalink && primary.permalink !== targetUrl) {
      const fallbackOpened = openExternalUrl(primary.permalink);
      if (fallbackOpened) {
        return;
      }
    }
    if (!opened && primary.permalink) {
      const copied = await copyToClipboard(primary.permalink);
      if (copied) {
        addToast("Couldn't open Slack, copied link instead.", "warning");
        return;
      }
    }
    if (!opened) {
      addToast("Unable to open Slack link.", "error");
    }
  };

  const handleCopy = async () => {
    if (!primary.permalink) {
      addToast("Slack link unavailable to copy.", "warning");
      return;
    }
    const copied = await copyToClipboard(primary.permalink);
    if (copied) {
      addToast("Slack link copied to clipboard.", "success");
    } else {
      addToast("Unable to copy Slack link.", "error");
    }
  };

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-[#131722] p-4 shadow-[0_12px_24px_rgba(0,0,0,0.45)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-white/50">Slack conversation</p>
          <p className="text-base font-semibold text-white">{channelLabel}</p>
          <p className="text-xs text-white/70">{primary.author ?? "Unknown author"}</p>
          {timestampLabel ? <p className="text-[11px] text-white/50">{timestampLabel}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleOpen}
            className="inline-flex items-center gap-2 rounded-full border border-white/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-white transition hover:border-white/40 hover:text-white/90"
          >
            Open Slack conversation
            <span aria-hidden="true">↗</span>
          </button>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-white/80 transition hover:border-white/30 hover:text-white"
          >
            Copy link
          </button>
        </div>
      </div>
    </div>
  );
};

function formatSlackSourceTimestamp(isoTime?: string, ts?: string): string | null {
  const iso = isoTime || (ts ? new Date(parseFloat(ts) * 1000).toISOString() : null);
  if (!iso) {
    return null;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const EvidenceList = ({ evidence }: { evidence?: EvidenceItem[] }) => (
  <div className="space-y-2">
    <h4 className="text-xs font-semibold uppercase tracking-wide text-white/60">Evidence</h4>
    {evidence && evidence.length ? (
      <div className="flex flex-wrap gap-2">
        {evidence.map((item, index) => {
          const key = item.evidence_id || `${item.title || item.source || "evidence"}-${index}`;
          const label = item.title || item.source || item.url || key;
          if (item.url) {
            return (
              <a
                key={key}
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-white/20 px-3 py-1 text-xs text-white/80 hover:border-white/40 hover:text-white"
              >
                {label}
              </a>
            );
          }
          return (
            <span key={key} className="rounded-full border border-white/15 px-3 py-1 text-xs text-white/70">
              {label}
            </span>
          );
        })}
      </div>
    ) : (
      <p className="text-xs text-white/70">Evidence pending or not recorded.</p>
    )}
  </div>
);

const ToolRunList = ({ toolRuns }: { toolRuns?: ToolRun[] }) => (
  <div className="space-y-2">
    <h4 className="text-xs font-semibold uppercase tracking-wide text-white/60">Tool runs</h4>
    {toolRuns && toolRuns.length ? (
      <div className="space-y-1 text-xs text-white/80">
        {toolRuns.map((run, index) => (
          <div key={run.step_id ?? `${run.tool}-${index}`} className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">{run.tool}</p>
              <p className="uppercase tracking-wide text-white/60">{run.status ?? "completed"}</p>
            </div>
            {run.output_preview ? (
              <p className="max-w-xs text-[11px] italic text-white/70">{run.output_preview}</p>
            ) : null}
          </div>
        ))}
      </div>
    ) : (
      <p className="text-xs text-white/70">No external tools recorded.</p>
    )}
  </div>
);
