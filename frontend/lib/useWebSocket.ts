import { useEffect, useRef, useState, useCallback } from "react";
import { validateMessage } from "./security";
import { wsMonitor, logStructured, createCorrelationId } from "./telemetry";

export interface PlanStep {
  id: number;
  action: string;
  parameters?: Record<string, any>;
  reasoning?: string;
  dependencies?: number[];
  expected_output?: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  sequence_number?: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
  output_preview?: string;
}

export interface PlanState {
  goal: string;
  steps: PlanStep[];
  activeStepId?: number;
  status: "planning" | "executing" | "completed" | "failed" | "cancelled";
  started_at?: string;
  completed_at?: string;
  last_sequence_number: number;
}

export interface SlashSlackTopic {
  topic: string;
  mentions?: number;
  sample?: string;
}

export interface SlashSlackDecision {
  text: string;
  timestamp?: string;
  participant?: string;
  participant_id?: string;
  permalink?: string;
}

export interface SlashSlackTask {
  description: string;
  timestamp?: string;
  assignee?: string;
  assignee_id?: string;
  permalink?: string;
}

export interface SlashSlackQuestion {
  text: string;
  timestamp?: string;
  participant?: string;
  permalink?: string;
}

export interface SlashSlackReference {
  kind: string;
  url: string;
  message_ts?: string;
}

export interface SlashSlackSections {
  topics?: SlashSlackTopic[];
  decisions?: SlashSlackDecision[];
  tasks?: SlashSlackTask[];
  open_questions?: SlashSlackQuestion[];
  references?: SlashSlackReference[];
}

export interface SlashSlackPayload {
  type: "slash_slack_summary";
  message: string;
  sections?: SlashSlackSections;
  context?: Record<string, any>;
  graph?: Record<string, any>;
  messages_preview?: Array<Record<string, any>>;
  metadata?: Record<string, any>;
}

export interface Message {
  type: "user" | "assistant" | "system" | "error" | "status" | "plan" | "bluesky_notification" | "apidocs_drift";
  message: string;
  timestamp: string;
  status?: string;
  goal?: string;
  toolName?: string; // Active tool being executed
  steps?: Array<{
    id: number;
    action: string;
    parameters?: Record<string, any>;
    reasoning?: string;
    dependencies?: number[];
    expected_output?: string;
  }>;
  files?: Array<{
    name: string;
    path: string;
    score: number;
    result_type?: "document" | "image";
    thumbnail_url?: string;
    preview_url?: string;
    meta?: {
      file_type?: string;
      total_pages?: number;
      width?: number;
      height?: number;
    };
  }>;
  documents?: Array<any>; // Document list format
  completion_event?: {
    action_type: string;
    summary: string;
    status: string;
    artifact_metadata?: {
      recipients?: string[];
      file_type?: string;
      file_size?: number;
      subject?: string;
      [key: string]: any;
    };
    artifacts?: string[];
  };
  bluesky_notification?: {
    source: "notification" | "timeline_mention";
    notification_type?: string;
    reason?: string;
    author_handle: string;
    author_name: string;
    timestamp: string;
    uri?: string;
    reason_subject?: string;
    subject_post?: any;
    post?: any;
  };
  // API Docs drift detection (Oqoqo pattern)
  apidocs_drift?: {
    has_drift: boolean;
    changes: Array<{
      change_type: string;
      severity: "breaking" | "non_breaking" | "cosmetic";
      endpoint: string;
      description: string;
      code_value?: string;
      spec_value?: string;
    }>;
    summary: string;
    proposed_spec?: string;
    change_count: number;
    breaking_changes: number;
  };
  slash_slack?: SlashSlackPayload;
}

interface UseWebSocketReturn {
  messages: Message[];
  isConnected: boolean;
  connectionState: "connecting" | "connected" | "reconnecting" | "error";
  lastError: string | null;
  planState: PlanState | null;
  sendMessage: (message: string) => void;
  sendCommand: (command: string, payload?: Record<string, unknown>) => void;
  clearMessages: () => void;
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<"connecting" | "connected" | "reconnecting" | "error">("connecting");
  const [lastError, setLastError] = useState<string | null>(null);
  const [planState, setPlanState] = useState<PlanState | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const reconnectAttemptsRef = useRef(0);
  const urlRef = useRef(url);
  const isUnmountedRef = useRef(false);
  // Message processing queue to ensure sequential handling
  const messageQueueRef = useRef<Array<{ data: any; timestamp: number }>>([]);
  const isProcessingQueueRef = useRef(false);

  // Update URL ref when it changes
  useEffect(() => {
    urlRef.current = url;
  }, [url]);

  const connect = useCallback(() => {
    console.log("🔄 connect() called");

    // Don't connect if component is unmounted
    if (isUnmountedRef.current) {
      console.log("❌ Component unmounted, skipping connection");
      return;
    }

    // Check if there's an existing connection
    if (wsRef.current) {
      const state = wsRef.current.readyState;
      console.log(`📊 Existing WebSocket state: ${state} (0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)`);

      // If already open or connecting, don't create new connection
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
        console.log("WebSocket already connected or connecting, skipping");
        return;
      }

      // If closing or closed, allow new connection to be created
      // but don't try to close it again
      if (state === WebSocket.CLOSING || state === WebSocket.CLOSED) {
        console.log("🗑️  Clearing closed/closing WebSocket reference");
        wsRef.current = null;
      }
    }

    console.log(`🚀 Creating new WebSocket connection to ${urlRef.current}`);

    try {
      const ws = new WebSocket(urlRef.current);

      ws.onopen = () => {
        if (isUnmountedRef.current) {
          console.log("WebSocket opened but component unmounted, closing");
          ws.close();
          return;
        }
        console.log("✅ WebSocket connected successfully");

        // Telemetry: Record successful connection
        wsMonitor.updateConnectionState("connected");
        logStructured("info", "WebSocket connection established");

        setIsConnected(true);
        setConnectionState("connected");
        setLastError(null);
        reconnectAttemptsRef.current = 0;

        // On reconnection, if we had a plan in progress, mark it as potentially recoverable
        // The backend will send updated plan state if the session is still active
        setPlanState((prevState) => {
          if (!prevState || prevState.status === "completed") return prevState;
          // If we reconnected and had a running plan, mark it as executing again
          // The backend will send plan_update events to resync state
          return {
            ...prevState,
            status: "executing", // Assume execution continues unless we get finalization
          };
        });
      };

      ws.onmessage = (event) => {
        if (isUnmountedRef.current) return;

        try {
          const data = JSON.parse(event.data);
          console.log("Received message:", data);

          // Handle clear command - clear all messages
          if (data.type === "clear") {
            setMessages([
              {
                type: "system",
                message: data.message || "✨ Context cleared. Starting a new session.",
                timestamp: data.timestamp || new Date().toISOString(),
              },
            ]);
            return;
          }

          // Map backend message types to our frontend types
          const rawType = typeof data.type === "string" ? data.type.toLowerCase() : "response";

          // Handle plan messages specially - they have goal/steps instead of message
          if (rawType === "plan") {
            // Initialize plan state with pending steps
            const initialSteps: PlanStep[] = (data.steps || []).map((step: any) => ({
              ...step,
              status: "pending" as const,
              sequence_number: 0,
            }));

            setPlanState({
              goal: data.goal ?? "",
              steps: initialSteps,
              status: "executing",
              started_at: data.timestamp || new Date().toISOString(),
              last_sequence_number: 0,
            });

            setMessages((prev) => [
              ...prev,
              {
                type: "plan",
                message: "",
                goal: data.goal ?? "",
                steps: Array.isArray(data.steps) ? data.steps : [],
                timestamp: data.timestamp || new Date().toISOString(),
              },
            ]);
            return;
          }

          // Handle plan update messages for live progress tracking
          if (rawType === "plan_update") {
            const sequenceNumber = data.sequence_number || 0;
            const stepId = data.step_id;
            const newStatus = data.status; // "running" | "completed" | "failed"
            const timestamp = data.timestamp || new Date().toISOString();

            setPlanState((prevState) => {
              if (!prevState) return null;

              // Skip out-of-order messages (only process if sequence number is newer)
              if (sequenceNumber <= prevState.last_sequence_number) {
                console.debug(`Skipping out-of-order plan update: seq ${sequenceNumber} <= ${prevState.last_sequence_number}`);
                return prevState;
              }

              const updatedSteps = prevState.steps.map((step) => {
                if (step.id === stepId) {
                  const updatedStep: PlanStep = {
                    ...step,
                    status: newStatus,
                    sequence_number: sequenceNumber,
                  };

                  if (newStatus === "running") {
                    updatedStep.started_at = timestamp;
                  } else if (newStatus === "completed" || newStatus === "failed") {
                    updatedStep.completed_at = timestamp;
                    if (data.output_preview) {
                      updatedStep.output_preview = data.output_preview;
                    }
                    if (data.error) {
                      updatedStep.error = data.error;
                    }
                  }

                  return updatedStep;
                }
                return step;
              });

              // Update active step ID
              let activeStepId = prevState.activeStepId;
              if (newStatus === "running") {
                activeStepId = stepId;
              } else if (newStatus === "completed" || newStatus === "failed") {
                activeStepId = undefined; // Clear active step when it finishes
              }

              return {
                ...prevState,
                steps: updatedSteps,
                activeStepId,
                last_sequence_number: sequenceNumber,
              };
            });
            return;
          }

          // Handle plan finalization
          if (rawType === "plan_finalize") {
            const timestamp = data.timestamp || new Date().toISOString();

            setPlanState((prevState) => {
              if (!prevState) return null;

              // Mark remaining pending steps as skipped
              const finalizedSteps = prevState.steps.map((step) => {
                if (step.status === "pending") {
                  return {
                    ...step,
                    status: "skipped" as const,
                    completed_at: timestamp,
                  };
                }
                return step;
              });

              return {
                ...prevState,
                steps: finalizedSteps,
                status: data.status || "completed",
                completed_at: timestamp,
                activeStepId: undefined,
              };
            });
            return;
          }

          // Handle Bluesky notifications
          if (rawType === "bluesky_notification") {
            const notificationData = data.data;
            const timestamp = data.timestamp || new Date().toISOString();

            // Create human-readable message for chat
            let messageText = "";
            let toastMessage = "";

            if (notificationData.source === "notification") {
              const reason = notificationData.reason || notificationData.notification_type || "unknown";
              const author = notificationData.author_name || `@${notificationData.author_handle}`;

              messageText = `🔔 Bluesky: ${author} ${reason}`;
              toastMessage = `${author} ${reason}`;

              // Add subject post info if available
              if (notificationData.subject_post) {
                const post = notificationData.subject_post;
                messageText += `\n"${post.text?.substring(0, 100)}${post.text?.length > 100 ? '...' : ''}"`;
                toastMessage += `: "${post.text?.substring(0, 50)}${post.text?.length > 50 ? '...' : ''}"`;
              }
            } else if (notificationData.source === "timeline_mention") {
              const post = notificationData.post;
              const author = post?.author_name || `@${post?.author_handle}`;

              messageText = `💬 Bluesky mention: ${author} mentioned you\n"${post?.text?.substring(0, 150)}${post?.text?.length > 150 ? '...' : ''}"`;
              toastMessage = `${author} mentioned you`;
            }

            // Add to chat as system message
            setMessages((prev) => [
              ...prev,
              {
                type: "bluesky_notification",
                message: messageText,
                timestamp: timestamp,
                bluesky_notification: notificationData,
              },
            ]);

            // TODO: Fire toast notification here when toast context is available
            // For now, we'll just log it
            console.log("🔔 Bluesky notification:", toastMessage);

            return;
          }

          // Handle API Docs drift notifications (Oqoqo pattern)
          if (rawType === "apidocs_drift" || data.type === "apidocs_drift") {
            const driftData = data.data || data;
            const timestamp = data.timestamp || new Date().toISOString();

            // Create human-readable message
            let messageText = "📄 API Documentation Drift Detected\n\n";
            messageText += driftData.summary || `${driftData.change_count || 0} change(s) found between code and documentation.`;

            // Add to chat
            setMessages((prev) => [
              ...prev,
              {
                type: "apidocs_drift",
                message: messageText,
                timestamp: timestamp,
                apidocs_drift: {
                  has_drift: driftData.has_drift ?? true,
                  changes: driftData.changes || [],
                  summary: driftData.summary || "",
                  proposed_spec: driftData.proposed_spec,
                  change_count: driftData.change_count || 0,
                  breaking_changes: driftData.breaking_changes || 0,
                },
              },
            ]);

            console.log("📄 API Docs drift detected:", driftData.summary);
            return;
          }

          // Handle Spotify playback updates - emit event for SpotifyMiniPlayer to refresh
          if (rawType === "spotify_playback_update") {
            console.log("🎵 Spotify playback update:", data.action);
            // Dispatch a custom event that SpotifyMiniPlayer listens for
            window.dispatchEvent(new CustomEvent('spotify:playback_update', { 
              detail: { action: data.action, timestamp: data.timestamp } 
            }));
            return;
          }

          let messageType: Message["type"] = "assistant";

          switch (rawType) {
            case "system":
              messageType = "system";
              break;
            case "error":
              messageType = "error";
              break;
            case "status":
              messageType = "status";
              break;
            case "help":
            case "palette":
            case "agents":
              messageType = "system";
              break;
            default:
              messageType = "assistant";
          }

          let slashSlackPayload: SlashSlackPayload | null = null;
          if (data.result && typeof data.result === "object" && data.result.type === "slash_slack_summary") {
            slashSlackPayload = data.result as SlashSlackPayload;
          }

          const payload =
            (slashSlackPayload?.message && slashSlackPayload.message.trim().length > 0)
              ? slashSlackPayload.message
              : typeof data.message === "string" && data.message.trim().length > 0
              ? data.message
              : typeof data.content === "string" && data.content.trim().length > 0
              ? data.content
              : data.result
              ? JSON.stringify(data.result, null, 2)
              : "";

          // CRITICAL: Don't skip messages that have files or completion_event, even if payload is empty
          // This ensures file lists and Bluesky post results are displayed even if message text is missing
          const hasFiles = data.files && Array.isArray(data.files) && data.files.length > 0;
          const hasCompletionEvent = data.completion_event;
          const hasDocuments = data.documents && Array.isArray(data.documents) && data.documents.length > 0;
          const hasSlashSlack = !!slashSlackPayload;
          
          // Skip empty payloads for non-status messages, UNLESS they have files/documents/completion_event
          if (!payload && messageType !== "status" && !hasFiles && !hasDocuments && !hasCompletionEvent && !hasSlashSlack) {
            console.log("[useWebSocket] Skipping message with empty payload and no files/documents/completion_event/slash_slack");
            return;
          }

          // Log when files are present for debugging
          if (hasFiles) {
            console.log(`[useWebSocket] Message has ${data.files.length} files:`, {
              messageType,
              hasPayload: !!payload,
              files: data.files.map((f: any) => ({ name: f.name, result_type: f.result_type }))
            });
          }

          setMessages((prev) => [
            ...prev,
            {
              type: messageType,
              message: payload,
              timestamp: data.timestamp || new Date().toISOString(),
              status: data.status,
              toolName: data.tool_name || data.toolName, // Extract tool name if present
              files: data.files || undefined, // Extract files array if present
              documents: data.documents || undefined, // Extract documents array if present
              completion_event: data.completion_event || undefined, // Extract completion event if present
              slash_slack: slashSlackPayload || undefined,
            },
          ]);
        } catch (error) {
          console.error("Error parsing message:", error);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);

        // Telemetry: Record connection error
        wsMonitor.recordConnectionFailure(new Error("WebSocket connection error"));
        logStructured("error", "WebSocket connection error occurred");

        if (!isUnmountedRef.current) {
          setIsConnected(false);
          setConnectionState("error");
          setLastError("WebSocket connection error occurred");
        }
      };

      ws.onclose = (event) => {
        console.log(`⛔ WebSocket closed (code: ${event.code}, reason: ${event.reason || 'none'})`);

        // Telemetry: Record disconnection
        wsMonitor.updateConnectionState("disconnected");
        logStructured("warning", "WebSocket connection closed", {
          code: event.code,
          reason: event.reason || 'none'
        });

        if (!isUnmountedRef.current) {
          setIsConnected(false);

          // Mark plan state as potentially stale on disconnection
          // Don't clear it immediately in case reconnection restores the session
          setPlanState((prevState) => {
            if (!prevState) return null;
            return {
              ...prevState,
              status: "failed", // Mark as failed until reconnected
            };
          });

          // Attempt to reconnect with exponential backoff
          if (reconnectAttemptsRef.current < 5) {
            const timeout = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
            reconnectAttemptsRef.current += 1;

            console.log(`⏰ Scheduling reconnect attempt ${reconnectAttemptsRef.current} in ${timeout}ms`);
            setConnectionState("reconnecting");

            reconnectTimeoutRef.current = setTimeout(() => {
              if (!isUnmountedRef.current) {
                console.log(`🔁 Reconnecting... (attempt ${reconnectAttemptsRef.current})`);
                connect();
              }
            }, timeout);
          } else {
            console.log("❌ Max reconnection attempts reached");
            setConnectionState("error");
            setLastError("Failed to reconnect after maximum attempts");
          }
        } else {
          console.log("Component unmounted, not reconnecting");
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error("Error creating WebSocket:", error);
      if (!isUnmountedRef.current) {
        setIsConnected(false);
        setConnectionState("error");
        setLastError("Failed to create WebSocket connection");
      }
    }
  }, []); // Empty deps - using refs for values

  useEffect(() => {
    isUnmountedRef.current = false;
    connect();

    return () => {
      isUnmountedRef.current = true;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      // Close WebSocket if it exists and is open/connecting
      if (wsRef.current) {
        const state = wsRef.current.readyState;
        if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
          wsRef.current.close();
        }
        wsRef.current = null;
      }
    };
  }, []); // Only run once on mount

  const sendMessage = useCallback((message: string) => {
    // Validate message before sending
    const validation = validateMessage(message);
    if (!validation.valid) {
      setMessages((prev) => [
        ...prev,
        {
          type: "error",
          message: validation.error || "Invalid message",
          timestamp: new Date().toISOString(),
        },
      ]);
      return;
    }

    const sanitizedMessage = validation.sanitized || message;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Handle /clear command - clear UI immediately before sending
      const normalizedMessage = sanitizedMessage.trim().toLowerCase();
      if (normalizedMessage === "/clear" || normalizedMessage === "clear") {
        // Clear messages immediately for better UX
        setMessages([]);
        // Still send to backend to clear session memory
        wsRef.current.send(JSON.stringify({ message: sanitizedMessage }));
        return;
      }

      // Add user message to the UI immediately
      const userMessage: Message = {
        type: "user",
        message: sanitizedMessage,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // Send to backend
      wsRef.current.send(JSON.stringify({ message: sanitizedMessage }));
    } else {
      console.error("WebSocket is not connected");
      setMessages((prev) => [
        ...prev,
        {
          type: "error",
          message: "Not connected to server. Please refresh the page.",
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  }, []);

  const sendCommand = useCallback((command: string, payload?: Record<string, unknown>) => {
    if (!command) {
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const body = {
        ...(payload || {}),
        command,
      };

      wsRef.current.send(JSON.stringify(body));

      if (command === "stop") {
        setMessages((prev) => [
          ...prev,
          {
            type: "status",
            message: "Stop requested. Attempting to cancel...",
            timestamp: new Date().toISOString(),
            status: "cancelling",
          },
        ]);
      }
    } else {
      console.error("WebSocket is not connected");
      setMessages((prev) => [
        ...prev,
        {
          type: "error",
          message: "Not connected to server. Please refresh the page.",
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setPlanState(null); // Clear plan state when conversation is reset
  }, []);

  return {
    messages,
    isConnected,
    connectionState,
    lastError,
    planState,
    sendMessage,
    sendCommand,
    clearMessages,
  };
}
