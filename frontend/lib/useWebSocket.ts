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

export interface SlashSlackSampleEvidence {
  channel?: string;
  snippet?: string;
}

export interface SlashSlackDebugPayload {
  source?: string;
  retrieved_count?: number;
  status?: string;
  sample_evidence?: SlashSlackSampleEvidence[];
}

export interface SlackSourceItem {
  id?: string;
  channel?: string;
  channel_id?: string;
  author?: string;
  ts?: string;
  iso_time?: string;
  permalink?: string;
  deep_link?: string;
  snippet?: string;
  rank?: number;
  thread_ts?: string;
}

export interface SlashSlackPayload {
  type: "slash_slack_summary";
  message: string;
  sections?: SlashSlackSections;
  context?: Record<string, any>;
  graph?: Record<string, any>;
  messages_preview?: Array<Record<string, any>>;
  metadata?: Record<string, any>;
  debug?: SlashSlackDebugPayload;
  sources?: SlackSourceItem[];
}

export interface SlashGitSourceItem {
  id?: string | number;
  type?: "commit" | "pr" | string;
  label?: string;
  rank?: number;
  repo?: string;
  repo_label?: string;
  component_label?: string | null;
  short_sha?: string;
  pr_number?: number;
  title?: string;
  author?: string;
  timestamp?: string;
  message?: string;
  snippet?: string;
  url?: string;
  files_changed?: string[];
  labels?: string[];
  service_ids?: string[];
  component_ids?: string[];
}

export interface SlashGitContext {
  repo_label?: string;
  component_label?: string | null;
  scope_label?: string;
  time_window_label?: string;
  mode?: string;
  graph_counts?: Record<string, number>;
  authors?: string[];
  top_files?: Array<{ path: string; touches: number }>;
  services?: string[];
  components?: string[];
  apis?: string[];
  labels?: string[];
  incident_signals?: Array<Record<string, any>>;
}

export interface SlashGitSummaryPayload {
  type: "slash_git_summary";
  status?: string;
  message: string;
  details?: string;
  data?: Record<string, any>;
  sources?: SlashGitSourceItem[];
  context?: SlashGitContext;
  analysis?: Record<string, any>;
  sections?: Array<Record<string, any>>;
  notable_prs?: Array<Record<string, any>>;
  breaking_changes?: Array<Record<string, any>>;
  next_actions?: Array<Record<string, any>>;
  references?: Array<Record<string, any>>;
  graph_context?: Record<string, any>;
  metadata?: Record<string, any>;
  debug?: SlashSlackDebugPayload;
}

export interface SlashCerebrosSummaryPayload {
  type: "slash_cerebros_summary";
  status?: string;
  message: string;
  context?: {
    modalities_used?: string[];
    total_results?: number;
    query_plan?: SlashQueryPlan;
    graph_context?: Record<string, any>;
  };
  sources?: CerebrosSource[];
  analysis?: Record<string, any>;
  cerebros_answer?: CerebrosAnswer;
  data?: Record<string, any>;
  incident_candidate?: IncidentCandidate;
  incident_id?: string;
}

export interface YouTubeEvidenceSnippet {
  timestamp?: string;
  start_seconds?: number;
  end_seconds?: number;
  text?: string;
}

export interface YouTubePayload {
  type?: "youtube_summary" | "result";
  status?: string;
  message: string;
  details?: string;
  data?: {
    video?: Record<string, any>;
    retrieval?: Record<string, any>;
    evidence?: YouTubeEvidenceSnippet[];
    trace_url?: string;
    cached?: boolean;
  };
}

export interface EvidenceItem {
  evidence_id?: string;
  source?: string;
  title?: string;
  url?: string;
  metadata?: Record<string, unknown>;
}

export interface DocPriority {
  doc_id?: string;
  doc_title?: string;
  doc_url?: string;
  score: number;
  reason?: string;
  severity?: string;
  impact_level?: string;
  issue_id?: string;
  severity_score?: number;
  severity_score_100?: number;
  severity_label?: string;
  severity_breakdown?: Record<string, number>;
  severity_details?: Record<string, any>;
}

export interface SourceDivergenceItem {
  source1?: string;
  source2?: string;
  description?: string;
}

export interface SourceDivergenceSummary {
  summary?: string;
  count?: number;
  items?: SourceDivergenceItem[];
}

export interface InformationGap {
  description: string;
  type?: string | null;
}

export interface CerebrosSource {
  type: "slack" | "git" | "doc" | "issue" | "youtube" | string;
  label: string;
  url: string;
  channel?: string;
  repo?: string;
  pr?: string | number;
  doc_id?: string;
  component?: string;
  tracker?: string;
  key?: string | number;
  snippet?: string;
  score?: number;
  timestamp?: string;
  modality?: string;
  rank?: number;
}

export interface CerebrosAnswer {
  answer: string;
  option?: "activity_graph" | "cross_system_context" | "generic";
  components?: string[] | null;
  sources?: CerebrosSource[];
  doc_priorities?: DocPriority[];
  root_cause_explanation?: string;
  impact_summary?: string;
  resolution_plan?: string[] | string;
  activity_signals?: Record<string, number>;
  dissatisfaction_signals?: Record<string, number>;
  dependency_impact?: Record<string, any>;
  source_divergence?: SourceDivergenceSummary;
  information_gaps?: InformationGap[];
}

export interface IncidentCandidateCounts {
  components?: number;
  docs?: number;
  issues?: number;
  slack_threads?: number;
  git_items?: number;
  evidence?: number;
}

export interface IncidentCandidate {
  investigation_id?: string;
  raw_trace_id?: string;
  query: string;
  summary: string;
  llm_explanation?: string;
  components?: string[];
  doc_priorities?: DocPriority[];
  sources_used?: string[];
  counts?: IncidentCandidateCounts;
  impacted_nodes?: Record<string, unknown>;
  incident_scope?: Record<string, unknown>;
  severity: "low" | "medium" | "high" | "critical";
  blast_radius_score?: number;
  source_command?: string;
  project_id?: string;
  issue_id?: string;
  recency_info?: {
    most_recent?: string;
    hours_since?: number;
  };
  modalities_used?: string[];
  root_cause_explanation?: string;
  impact_summary?: string;
  resolution_plan?: string | string[];
  activity_signals?: Record<string, number>;
  dissatisfaction_signals?: Record<string, number>;
  dependency_impact?: Record<string, any>;
  source_divergence?: SourceDivergenceSummary;
  information_gaps?: InformationGap[];
  incident_entities?: Array<Record<string, any>>;
}

export interface ToolRun {
  step_id?: string;
  tool: string;
  status?: string;
  output_preview?: string;
}

export interface SlashQueryPlanTarget {
  raw?: string;
  type?: string;
  identifier?: string;
  label?: string;
}

export interface SlashQueryPlan {
  intent?: string;
  tone?: string;
  format_hint?: string;
  hashtags?: string[];
  required_outputs?: string[];
  time_scope?: Record<string, unknown>;
  targets?: SlashQueryPlanTarget[];
}

function normalizeEvidence(raw: unknown): EvidenceItem[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      evidence_id: (item.evidence_id as string) ?? (item.id as string),
      source: item.source as string | undefined,
      title: item.title as string | undefined,
      url: item.url as string | undefined,
      metadata: (item.metadata as Record<string, unknown>) ?? undefined,
    }));
}

function cerebrosSourcesToEvidenceItems(sources: CerebrosSource[]): EvidenceItem[] {
  if (!Array.isArray(sources)) {
    return [];
  }
  return sources
    .filter((source) => source && typeof source.url === "string")
    .map((source, index) => {
      const metadata: Record<string, unknown> = {};
      if (source.channel) metadata.channel = source.channel;
      if (source.repo) metadata.repo = source.repo;
      if (source.pr !== undefined) metadata.pr = source.pr;
      if (source.component) metadata.component = source.component;
      if (source.tracker) metadata.tracker = source.tracker;
      if (source.key) metadata.key = source.key;
      return {
        evidence_id: source.doc_id || source.url || `${source.type}-${index}`,
        source: source.type,
        title: source.label,
        url: source.url,
        metadata,
      };
    });
}

function emitGraphHighlights(graphData: any) {
  if (typeof window === "undefined" || !graphData) return;
  const nodeIds = new Set<string>();
  if (Array.isArray(graphData?.nodes)) {
    graphData.nodes.forEach((node: any) => {
      if (typeof node?.id === "string") {
        nodeIds.add(node.id);
      }
    });
  }
  if (Array.isArray(graphData?.highlight_node_ids)) {
    graphData.highlight_node_ids.forEach((nodeId: any) => {
      if (typeof nodeId === "string") {
        nodeIds.add(nodeId);
      }
    });
  }
  if (!nodeIds.size) return;
  window.dispatchEvent(new CustomEvent("graph:highlight", { detail: { nodeIds: Array.from(nodeIds) } }));
}

const SLACK_SCOPE_REGEX = /#([A-Za-z0-9._-]+)/gi;

function extractSlackScopes(text: string): string[] {
  if (!text) {
    return [];
  }
  const scopes = new Set<string>();
  let match: RegExpExecArray | null;
  const normalized = text.toLowerCase();
  while ((match = SLACK_SCOPE_REGEX.exec(normalized)) !== null) {
    const token = match[1];
    if (token) {
      scopes.add(`#${token}`);
    }
  }
  return Array.from(scopes);
}

export function mapServerPayloadToMessage(data: any): Message | null {
  if (!data || typeof data !== "object") {
    return null;
  }

  const rawType = typeof data.type === "string" ? data.type.toLowerCase() : "response";
  let messageType: Message["type"] = "assistant";

  if (rawType === "plan_finalize") {
    const status = typeof data.status === "string" ? data.status.toLowerCase() : "";
    const msg =
      status === "completed"
        ? "Task completed."
        : status === "failed" || status === "error"
        ? data.error || "Task failed."
        : data.message || "";
    return {
      type: "status",
      message: msg,
      timestamp: data.timestamp || new Date().toISOString(),
      status: status || "completed",
    };
  }

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
    emitGraphHighlights(slashSlackPayload.graph);
  }

  let slashGitPayload: SlashGitSummaryPayload | null = null;
  const slashGitCandidate =
    (data.result && typeof data.result === "object" && data.result.type === "slash_git_summary"
      ? (data.result as SlashGitSummaryPayload)
      : rawType === "slash_git_summary"
      ? (data as SlashGitSummaryPayload)
      : null);
  if (slashGitCandidate) {
    slashGitPayload = {
      ...slashGitCandidate,
      sources: Array.isArray(slashGitCandidate.sources)
        ? slashGitCandidate.sources
        : Array.isArray(data.sources)
        ? (data.sources as SlashGitSourceItem[])
        : undefined,
      context: slashGitCandidate.context || data.context,
      debug: slashGitCandidate.debug || data.debug,
    };
  }

  let slashCerebrosPayload: SlashCerebrosSummaryPayload | null = null;
  const slashCerebrosCandidate =
    (data.result && typeof data.result === "object" && data.result.type === "slash_cerebros_summary"
      ? (data.result as SlashCerebrosSummaryPayload)
      : rawType === "slash_cerebros_summary"
      ? (data as SlashCerebrosSummaryPayload)
      : null);
  if (slashCerebrosCandidate) {
    slashCerebrosPayload = {
      ...slashCerebrosCandidate,
      sources: Array.isArray(slashCerebrosCandidate.sources) ? slashCerebrosCandidate.sources : [],
      context: slashCerebrosCandidate.context || undefined,
    };
  }

  let youtubePayload: YouTubePayload | null = null;
  if (data.agent === "youtube" || rawType === "youtube_summary") {
    const resultObj = (data.result && typeof data.result === "object") ? data.result : data;
    youtubePayload = {
      type: resultObj.type as any,
      status: resultObj.status,
      message: resultObj.message,
      details: resultObj.details,
      data: resultObj.data,
    };
  }

  const responseData = typeof data.data === "object" && data.data !== null ? data.data : undefined;
  const cerebrosAnswer: CerebrosAnswer | undefined =
    (responseData?.cerebros_answer as CerebrosAnswer | undefined) ??
    (data.cerebros_answer as CerebrosAnswer | undefined);
  const detailsText = typeof data.details === "string" && data.details.trim().length > 0 ? data.details : undefined;
  const command = typeof data.command === "string" ? data.command.toLowerCase() : undefined;
  const agent = typeof data.agent === "string" ? data.agent.toLowerCase() : undefined;
  const brainTraceUrl = responseData?.brain_trace_url || data.brain_trace_url;
  const brainUniverseUrl = responseData?.brain_universe_url || data.brain_universe_url;
  const queryId = responseData?.query_id || data.query_id;

  const cerebrosAnswerText =
    cerebrosAnswer && typeof cerebrosAnswer.answer === "string" && cerebrosAnswer.answer.trim().length > 0
      ? cerebrosAnswer.answer
      : undefined;

  const payload =
    cerebrosAnswerText ??
    (slashSlackPayload?.message && slashSlackPayload.message.trim().length > 0
      ? slashSlackPayload.message
      : slashGitPayload?.message && slashGitPayload.message.trim().length > 0
      ? slashGitPayload.message
      : youtubePayload?.message && youtubePayload.message.trim().length > 0
      ? youtubePayload.message
      : typeof data.message === "string" && data.message.trim().length > 0
      ? data.message
      : typeof data.content === "string" && data.content.trim().length > 0
      ? data.content
      : data.result
      ? JSON.stringify(data.result, null, 2)
      : "");

  const hasFiles = Array.isArray(data.files) && data.files.length > 0;
  const hasDocuments = Array.isArray(data.documents) && data.documents.length > 0;
  const hasCompletionEvent = Boolean(data.completion_event);
  const hasSlashSlack = Boolean(slashSlackPayload);

  if (!payload && messageType !== "status" && !hasFiles && !hasDocuments && !hasCompletionEvent && !hasSlashSlack) {
    return null;
  }

  let normalizedEvidence = normalizeEvidence(data.evidence);
  const combinedCerebrosSources: CerebrosSource[] = [];
  if (slashCerebrosPayload?.sources?.length) {
    combinedCerebrosSources.push(...slashCerebrosPayload.sources);
  }
  if (Array.isArray(cerebrosAnswer?.sources)) {
    combinedCerebrosSources.push(...(cerebrosAnswer.sources as CerebrosSource[]));
  }
  if (combinedCerebrosSources.length) {
    normalizedEvidence = [
      ...cerebrosSourcesToEvidenceItems(combinedCerebrosSources),
      ...normalizedEvidence,
    ];
  }
  const toolRuns = Array.isArray(data.tool_runs)
    ? (data.tool_runs as ToolRun[])
    : undefined;
  const componentIds = Array.isArray(data.component_ids)
    ? data.component_ids.map((id: any) => String(id))
    : undefined;
  const investigationId = data.investigation_id || data.investigationId;

  const queryPlan: SlashQueryPlan | undefined =
    (slashSlackPayload?.metadata as Record<string, any> | undefined)?.query_plan ||
    (responseData?.query_plan as SlashQueryPlan | undefined) ||
    (data.metadata?.query_plan as SlashQueryPlan | undefined);

  const graphContext = responseData?.graph_context || data.graph_context;
  emitGraphHighlights(graphContext);

  const incidentCandidate: IncidentCandidate | undefined =
    (data.incident_candidate as IncidentCandidate | undefined) ||
    (typeof data.result === "object" && data.result
      ? ((data.result as Record<string, any>).incident_candidate as IncidentCandidate | undefined)
      : undefined);
  const incidentId =
    data.incident_id ||
    (typeof data.result === "object" && data.result
      ? (data.result as Record<string, any>).incident_id
      : undefined);

  return {
    type: messageType,
    message: payload,
    timestamp: data.timestamp || new Date().toISOString(),
    status: data.status,
    agent,
    command,
    toolName: data.tool_name || data.toolName,
    files: data.files || undefined,
    documents: data.documents || undefined,
    completion_event: data.completion_event || undefined,
    slash_slack: slashSlackPayload || undefined,
    slash_git: slashGitPayload || undefined,
    slash_cerebros: slashCerebrosPayload || undefined,
    youtube: youtubePayload || undefined,
    evidence: normalizedEvidence.length ? normalizedEvidence : undefined,
    investigationId,
    componentIds,
    toolRuns,
    brainTraceUrl: brainTraceUrl || undefined,
    brainUniverseUrl: brainUniverseUrl || undefined,
    queryId: queryId || undefined,
    details: detailsText,
    queryPlan,
    graphContext,
    cerebrosAnswer: cerebrosAnswer,
    incidentCandidate,
    incidentId: incidentId || undefined,
  };
}

export interface Message {
  type: "user" | "assistant" | "system" | "error" | "status" | "plan" | "bluesky_notification" | "apidocs_drift";
  message: string;
  timestamp: string;
  status?: string;
  placeholderType?: string;
  agent?: string;
  command?: string;
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
  evidence?: EvidenceItem[];
  investigationId?: string;
  componentIds?: string[];
  toolRuns?: ToolRun[];
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
  slash_git?: SlashGitSummaryPayload;
  slash_cerebros?: SlashCerebrosSummaryPayload;
  youtube?: YouTubePayload;
  brainTraceUrl?: string;
  brainUniverseUrl?: string;
  queryId?: string;
  details?: string;
  queryPlan?: SlashQueryPlan;
  graphContext?: Record<string, any>;
  cerebrosAnswer?: CerebrosAnswer;
  incidentCandidate?: IncidentCandidate;
  incidentId?: string;
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
  const slackPlaceholderRef = useRef(false);

  // Update URL ref when it changes
  useEffect(() => {
    urlRef.current = url;
  }, [url]);

  const connect = useCallback(() => {
    console.log("🔄 connect() called");

    const targetUrl = urlRef.current;
    if (!targetUrl) {
      console.log("ℹ️ No WebSocket URL configured, skipping connection attempt");
      return;
    }

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
        if (wsRef.current.url === targetUrl) {
          console.log("WebSocket already connected or connecting, skipping");
          return;
        }
        console.log("🌐 WebSocket URL changed, closing prior connection");
        wsRef.current.close();
      }

      // If closing or closed, allow new connection to be created
      // but don't try to close it again
      if (state === WebSocket.CLOSING || state === WebSocket.CLOSED) {
        console.log("🗑️  Clearing closed/closing WebSocket reference");
        wsRef.current = null;
      }
    }

    console.log(`🚀 Creating new WebSocket connection to ${targetUrl}`);

    try {
      const ws = new WebSocket(targetUrl);

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

          const mappedMessage = mapServerPayloadToMessage(data);
          if (!mappedMessage) {
            console.log("[useWebSocket] Skipping message with empty payload and no files/documents/completion_event/slash_slack");
            return;
          }

          if (mappedMessage.files && mappedMessage.files.length > 0) {
            console.log(`[useWebSocket] Message has ${mappedMessage.files.length} files:`, {
              messageType: mappedMessage.type,
              hasPayload: Boolean(mappedMessage.message),
              files: mappedMessage.files.map((f: any) => ({ name: f.name, result_type: f.result_type }))
            });
          }

          const shouldClearSlackPlaceholders =
            Boolean(mappedMessage.slash_slack) || (mappedMessage.type === "error" && mappedMessage.agent === "slack");

          setMessages((prev) => {
            let baseMessages =
            mappedMessage.type === "status"
                ? prev.filter((msg) => msg.type !== "status" || msg.placeholderType === "slash_slack_status")
              : prev;

            if (shouldClearSlackPlaceholders && slackPlaceholderRef.current) {
              baseMessages = baseMessages.filter((msg) => msg.placeholderType !== "slash_slack_status");
              slackPlaceholderRef.current = false;
            }

          const updated = [...baseMessages, mappedMessage];

            if (rawType === "plan_finalize") {
              const lastIndex = updated.length - 1;
              if (lastIndex >= 0 && updated[lastIndex].type === "status" && updated[lastIndex].status === "processing") {
                updated[lastIndex] = {
                  ...updated[lastIndex],
                  status: data.status || "completed",
                  message:
                    data.status === "failed"
                      ? data.error || "Task failed."
                      : "Task completed.",
                };
              }
            }

            return updated;
          });
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

  useEffect(() => {
    if (isUnmountedRef.current) {
      return;
    }

    if (!url) {
      console.log("ℹ️ WebSocket URL not provided; ensuring connection is closed");
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
      setConnectionState("connecting");
      return;
    }

    setConnectionState("connecting");
    connect();
  }, [url, connect]);

  const addSlackPlaceholderMessages = useCallback(
    (scopes: string[]) => {
      const scopeLabel = scopes.length ? scopes.join(", ") : null;
      const timestamp = new Date().toISOString();
      const placeholders: Message[] = [
        {
          type: "status",
          message: scopeLabel
            ? `Answering via Slack context (scoped to ${scopeLabel})`
            : "Answering via Slack context…",
          status: "processing",
          timestamp,
          agent: "slack",
          placeholderType: "slash_slack_status",
        },
        {
          type: "status",
          message: scopeLabel
            ? `Fetching from Slack sources in ${scopeLabel}`
            : "Fetching from Slack sources…",
          status: "processing",
          timestamp,
          agent: "slack",
          placeholderType: "slash_slack_status",
        },
      ];
      slackPlaceholderRef.current = true;
      setMessages((prev) => {
        const withoutOld = prev.filter((msg) => msg.placeholderType !== "slash_slack_status");
        return [...withoutOld, ...placeholders];
      });
    },
    [setMessages]
  );

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
      const scopes = extractSlackScopes(sanitizedMessage);
      if (sanitizedMessage.trim().toLowerCase().startsWith("/slack")) {
        addSlackPlaceholderMessages(scopes);
      }
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
