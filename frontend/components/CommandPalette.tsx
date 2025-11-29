"use client";

import { useState, useEffect, useCallback, useMemo, useRef, KeyboardEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/apiConfig";
import { overlayFade, modalSlideDown } from "@/lib/motion";
import { duration, easing } from "@/lib/motion";
import logger from "@/lib/logger";
import { isElectron, hideWindow, revealInFinder, lockWindow, unlockWindow, openExpandedWindow } from "@/lib/electron";
import SpotifyMiniPlayer from "@/components/SpotifyMiniPlayer";
import RecordingIndicator from "@/components/RecordingIndicator";
import TypingIndicator from "@/components/TypingIndicator";
import PlanProgressRail from "@/components/PlanProgressRail";
import BlueskyNotificationCard from "@/components/BlueskyNotificationCard";
import LauncherHistoryPanel from "@/components/LauncherHistoryPanel";
import SettingsModal from "@/components/SettingsModal";
import { useVoiceRecorder } from "@/lib/useVoiceRecorder";
import { useWebSocket, Message, PlanState } from "@/lib/useWebSocket";
import { useCommandRouter, CommandRouterContext } from "@/lib/useCommandRouter";
import { isCalculation, evaluateCalculation, getRawResult } from "@/lib/useCalculator";

interface SearchResult {
  result_type: "document" | "image";
  file_path: string;
  file_name: string;
  file_type: string;
  page_number?: number;
  total_pages?: number;
  similarity_score: number;
  snippet: string;
  highlight_offsets: [number, number][];
  breadcrumb: string;
  thumbnail_url?: string;
  preview_url?: string;
  metadata?: {
    width?: number;
    height?: number;
  };
}

interface Command {
  id: string;
  title: string;
  description: string;
  category: string;
  icon: string;
  keywords: string[];
  handler_type: "agent" | "system" | "spotify_control" | "slash_command";
  endpoint?: string; // For spotify_control commands
  command_type?: "immediate" | "with_input"; // For slash commands
  placeholder?: string; // For slash commands with input
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onMount?: (inputRef: HTMLInputElement | null) => void;
  onOpenDocument?: (filePath: string, highlightOffsets?: [number, number][]) => void;
  onOpenExternal?: (filePath: string) => void;
  initialQuery?: string;
  source?: "files" | "folder";
  mode?: "overlay" | "launcher";
}

const MIN_MINI_CONVO_TURNS = 1;
const MAX_MINI_CONVO_TURNS = 5;
const DEFAULT_MINI_CONVO_TURNS = 2;

const clampMiniConversationDepth = (value: number) =>
  Math.min(Math.max(value, MIN_MINI_CONVO_TURNS), MAX_MINI_CONVO_TURNS);

export default function CommandPalette({
  isOpen,
  onClose,
  onMount,
  onOpenDocument,
  onOpenExternal,
  initialQuery = "",
  source = "files",
  mode = "overlay"
}: CommandPaletteProps) {
  const baseUrl = getApiBaseUrl();
  const inputRef = useRef<HTMLInputElement>(null);
  const commandInputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [commands, setCommands] = useState<Command[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [previewMode, setPreviewMode] = useState<'closed' | 'loading' | 'previewing'>('closed');
  const [previewData, setPreviewData] = useState<SearchResult | null>(null);
  const [showingResults, setShowingResults] = useState<"commands" | "files" | "both">("both");
  
  // View state: "search" (default) or "command_input" (for command arguments)
  const [viewState, setViewState] = useState<"search" | "command_input">("search");
  const [selectedCommand, setSelectedCommand] = useState<Command | null>(null);
  const [commandArg, setCommandArg] = useState("");

  // Voice recording state (only in launcher mode)
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const [miniConversationTurns, setMiniConversationTurns] = useState(DEFAULT_MINI_CONVO_TURNS);

  // Settings modal state
  const [showSettings, setShowSettings] = useState(false);

  // Transcribe audio to text
  const transcribeAudio = useCallback(async (audioBlob: Blob) => {
    logger.info("[LAUNCHER] Starting audio transcription");
    setIsTranscribing(true);
    try {
      if (!audioBlob || audioBlob.size === 0) {
        throw new Error("No audio recorded");
      }

      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");

      const response = await fetch(`${baseUrl}/api/transcribe`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Transcription failed: ${response.status}`);
      }

      const data = await response.json();
      const transcribedText = data.text?.trim() || "";
      
      logger.info("[LAUNCHER] Transcription complete", { text: transcribedText });
      
      if (transcribedText) {
        setQuery(transcribedText);
        // Focus the input after setting the query
        setTimeout(() => inputRef.current?.focus(), 50);
      }
    } catch (error) {
      logger.error("[LAUNCHER] Transcription error", { error });
      setVoiceError(error instanceof Error ? error.message : "Transcription failed");
    } finally {
      setIsTranscribing(false);
      // Unlock window after transcription (will be locked again if user submits)
      unlockWindow();
    }
  }, [baseUrl]);

  // Handle auto-stop from voice activity detection
  const handleAutoStopTranscription = useCallback(async (audioBlob: Blob) => {
    logger.info("[LAUNCHER] Voice auto-stop triggered");
    await transcribeAudio(audioBlob);
  }, [transcribeAudio]);

  // Voice recorder hook
  const { isRecording, startRecording, stopRecording, error: voiceRecorderError } = useVoiceRecorder({
    onAutoStop: handleAutoStopTranscription,
  });

  // Handle voice recording toggle
  const handleVoiceRecord = useCallback(async () => {
    if (isRecording) {
      logger.info("[LAUNCHER] Stopping voice recording");
      try {
        const audioBlob = await stopRecording();
        if (audioBlob) {
          await transcribeAudio(audioBlob);
        }
      } catch (err) {
        logger.error("[LAUNCHER] Error stopping recording", { error: err });
        unlockWindow(); // Unlock on error
      }
    } else {
      logger.info("[LAUNCHER] Starting voice recording");
      setVoiceError(null);
      // Lock window during voice recording
      lockWindow();
      try {
        await startRecording();
      } catch (err) {
        logger.error("[LAUNCHER] Error starting recording", { error: err });
        unlockWindow(); // Unlock on error
      }
    }
  }, [isRecording, startRecording, stopRecording, transcribeAudio]);

  // Handle stop recording from RecordingIndicator
  const handleStopRecording = useCallback(async () => {
    if (isRecording) {
      logger.info("[LAUNCHER] Stop recording from indicator");
      try {
        const audioBlob = await stopRecording();
        if (audioBlob) {
          await transcribeAudio(audioBlob);
        }
      } catch (err) {
        logger.error("[LAUNCHER] Error stopping recording from indicator", { error: err });
      }
    }
  }, [isRecording, stopRecording, transcribeAudio]);

  // WebSocket connection for chat responses (only in launcher mode)
  const wsUrl = mode === "launcher" ? `${baseUrl.replace('http', 'ws')}/ws/chat` : "";
  const { 
    messages: chatMessages, 
    sendMessage: wsSendMessage, 
    sendCommand: wsSendCommand,
    planState,
    isConnected: wsConnected,
    connectionState 
  } = useWebSocket(wsUrl);

  // State to track if history has been loaded for this session
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const sessionIdRef = useRef<string | null>(null);

  // Load conversation history on WebSocket connection
  const loadConversationHistory = useCallback(async () => {
    // CRITICAL: Don't block on historyLoaded - allow window to render
    // History loading should never prevent the window from displaying
    if (!wsConnected || mode !== "launcher") {
      return;
    }

    // Skip if already loaded or currently loading
    if (historyLoaded) {
      return;
    }

    try {
      // Extract session ID from WebSocket URL query params
      const urlObj = new URL(wsUrl, window.location.origin);
      const sessionId = urlObj.searchParams.get('session_id') || 'default';

      // Store session ID for reference
      sessionIdRef.current = sessionId;

      logger.info('[HISTORY] Loading conversation history', { sessionId });

      const response = await fetch(`${baseUrl}/api/conversation/history/${sessionId}`);

      if (!response.ok) {
        logger.warn('[HISTORY] Failed to load history', { status: response.status });
        setHistoryLoaded(true); // Mark as loaded even on error to prevent retries
        return;
      }

      const data = await response.json();
      logger.info('[HISTORY] Loaded messages', {
        count: data.messages?.length || 0,
        total: data.total_messages
      });

      // If we have historical messages, they're already in chatMessages from the backend
      // The backend WebSocket connection should handle this
      // For now, just mark as loaded
      setHistoryLoaded(true);

    } catch (error) {
      logger.error('[HISTORY] Failed to load conversation history', { error });
      setHistoryLoaded(true); // Mark as loaded to prevent infinite retries
    }
  }, [wsConnected, historyLoaded, mode, wsUrl, baseUrl]);

  // Load history when WebSocket connects
  useEffect(() => {
    if (wsConnected && !historyLoaded && mode === "launcher") {
      // Small delay to ensure WebSocket is fully established
      const timer = setTimeout(() => {
        loadConversationHistory();
      }, 500);

      return () => clearTimeout(timer);
    }
  }, [wsConnected, historyLoaded, mode, loadConversationHistory]);

  // Reset history loaded flag when session changes or component remounts
  useEffect(() => {
    setHistoryLoaded(false);
  }, [wsUrl]);

  // Deterministic command router for fast, local command handling
  const { routeCommand } = useCommandRouter();

  // Track if we're processing a query
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentResponse, setCurrentResponse] = useState<string>("");
  const [submittedQuery, setSubmittedQuery] = useState<string>(""); // Track what was submitted

  // Watch for new assistant messages
  useEffect(() => {
    if (mode !== "launcher" || chatMessages.length === 0) return;

    const lastMessage = chatMessages[chatMessages.length - 1];
    
    // Log all message types for debugging
    logger.debug("[LAUNCHER] New message received", { 
      type: lastMessage.type, 
      hasBluesky: !!lastMessage.bluesky_notification,
      hasFiles: !!lastMessage.files?.length,
      status: lastMessage.status 
    });
    
    // Update processing state based on message type
    if (lastMessage.type === "status") {
      const isActive = lastMessage.status === "processing" || lastMessage.status === "thinking";
      setIsProcessing(isActive);
      logger.info("[LAUNCHER] Status update", { status: lastMessage.status, isActive });
      
      // Unlock window when status indicates completion
      if (!isActive && (lastMessage.status === "complete" || lastMessage.status === "error" || lastMessage.status === "cancelled")) {
        unlockWindow();
      }
    }
    
    // Capture assistant response
    if (lastMessage.type === "assistant" && lastMessage.message) {
      setCurrentResponse(lastMessage.message);
      setIsProcessing(false);
      logger.info("[LAUNCHER] Assistant response received", { length: lastMessage.message.length });
      // Unlock window now that we have a response
      unlockWindow();
    }
    
    // Log Bluesky notifications
    if (lastMessage.type === "bluesky_notification" && lastMessage.bluesky_notification) {
      logger.info("[LAUNCHER] Bluesky notification received", { 
        author: lastMessage.bluesky_notification.author_handle,
        source: lastMessage.bluesky_notification.source 
      });
    }
    
    // Log file results
    if (lastMessage.files && lastMessage.files.length > 0) {
      logger.info("[LAUNCHER] File results received", { count: lastMessage.files.length });
    }
  }, [chatMessages, mode]);

  // Log WebSocket connection state changes
  useEffect(() => {
    if (mode === "launcher") {
      logger.info("[LAUNCHER] WebSocket state", { 
        connected: wsConnected, 
        state: connectionState,
        url: wsUrl 
      });
    }
  }, [wsConnected, connectionState, mode, wsUrl]);

  // Log plan state changes (orchestration visibility)
  useEffect(() => {
    if (mode === "launcher" && planState) {
      const completedSteps = planState.steps.filter(s => s.status === "completed").length;
      const runningStep = planState.steps.find(s => s.status === "running");
      logger.info("[LAUNCHER] Plan state changed", { 
        status: planState.status,
        goal: planState.goal,
        totalSteps: planState.steps.length,
        completedSteps,
        runningStepAction: runningStep?.action || null
      });
    }
  }, [planState, mode]);

  // Handle submitting a query to the chat
  const handleSubmitQuery = useCallback(async () => {
    if (!query.trim()) {
      logger.debug("[LAUNCHER] Empty query, ignoring");
      return;
    }
    
    const trimmedQuery = query.trim();
    logger.info("[LAUNCHER] Submitting query", { query: trimmedQuery, timestamp: Date.now() });
    
    // Lock window visibility to prevent blur from hiding during processing
    lockWindow();
    
    // Build context for command routing
    const routerContext: CommandRouterContext = {
      isMusicPlaying: false, // TODO: Get from Spotify state
      hasActivePlan: planState?.status === "executing" || planState?.status === "planning",
      isRecording: isRecording,
      isExpandedView: false,
    };
    
    // Try deterministic routing first
    const routeResult = await routeCommand(trimmedQuery, routerContext);
    
    if (routeResult.handled) {
      logger.info("[LAUNCHER] Command handled by deterministic router", { 
        action: routeResult.action,
        response: routeResult.response 
      });
      
      // Handle special actions
      if (routeResult.action === "clear") {
        wsSendMessage("/clear");
        setQuery("");
        unlockWindow();
        return;
      }
      
      if (routeResult.action === "cancel_plan") {
        wsSendCommand("stop");
        unlockWindow();
        return;
      }
      
      if (routeResult.action === "stop_recording" && isRecording) {
        handleStopRecording();
        unlockWindow();
        return;
      }
      
      if (routeResult.action === "help" && routeResult.response) {
        // Show help locally
        setCurrentResponse(routeResult.response);
        setSubmittedQuery(trimmedQuery);
        unlockWindow();
        return;
      }
      
      // Open settings modal
      if (routeResult.action === "open_settings") {
        setShowSettings(true);
        setQuery("");
        unlockWindow();
        return;
      }
      
      // For "open app" actions, show feedback
      if (routeResult.action === "open_app" && routeResult.response) {
        setCurrentResponse(routeResult.response);
        setSubmittedQuery(trimmedQuery);
        setQuery("");
        unlockWindow();
        return;
      }
      
      // For Spotify actions, show feedback
      if (routeResult.action?.startsWith("spotify_") && routeResult.response) {
        setCurrentResponse(routeResult.response);
        setSubmittedQuery(trimmedQuery);
        unlockWindow();
        return;
      }
      
      unlockWindow();
      return;
    }
    
    // Not deterministically routed - send to LLM via WebSocket
    if (!wsConnected) {
      logger.warn("[LAUNCHER] Cannot submit - WebSocket not connected", { state: connectionState });
      unlockWindow();
      return;
    }
    
    setIsProcessing(true);
    setCurrentResponse("");
    setSubmittedQuery(trimmedQuery); // Track what was submitted
    wsSendMessage(trimmedQuery);
    // Don't clear query - let user see what they typed
  }, [query, wsConnected, connectionState, wsSendMessage, wsSendCommand, routeCommand, planState, isRecording, handleStopRecording]);

  // Notify parent about the input ref for focus management
  useEffect(() => {
    if (onMount && inputRef.current) {
      onMount(inputRef.current);
    }
  }, [onMount]);

  // Define handler functions before useEffect to avoid initialization errors
  const handleSelectResult = useCallback((result: SearchResult) => {
    if (onOpenDocument) {
      onOpenDocument(result.file_path, result.highlight_offsets);
    }
    // DON'T close - Raycast-style behavior keeps window open
    logger.info("[LAUNCHER] Opened document", { path: result.file_path });
  }, [onOpenDocument]);

  const handleOpenExternal = useCallback(async (result: SearchResult) => {
    if (onOpenExternal) {
      onOpenExternal(result.file_path);
    } else if (isElectron()) {
      // Use Electron API to reveal in Finder
      revealInFinder(result.file_path);
    } else {
      // Fallback: Use the reveal-file API
      try {
        const response = await fetch(`${baseUrl}/api/reveal-file`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ path: result.file_path }),
        });

        if (!response.ok) {
          throw new Error('Failed to open externally');
        }
      } catch (error) {
        console.error('Error opening file externally:', error);
      }
    }
    // DON'T close - Raycast-style behavior keeps window open
    logger.info("[LAUNCHER] Opened file externally", { path: result.file_path });
  }, [onOpenExternal, baseUrl]);

  const togglePreview = useCallback((result: SearchResult) => {
    if (previewMode === 'closed' || previewData?.file_path !== result.file_path) {
      setPreviewMode('loading');
      setPreviewData(result);
      // Simulate loading delay for now
      setTimeout(() => setPreviewMode('previewing'), 300);
    } else {
      setPreviewMode('closed');
      setPreviewData(null);
    }
  }, [previewMode, previewData]);

  const handleExecuteCommand = useCallback(async (command: Command, argument?: string) => {
    logger.info("[COMMAND PALETTE] Executing command", { command: command.id, argument });

    // For slash commands with input, show input view instead of executing
    if (command.handler_type === "slash_command" && command.command_type === "with_input" && argument === undefined) {
      setSelectedCommand(command);
      setCommandArg("");
      setViewState("command_input");
      // Focus the command input after a short delay
      setTimeout(() => {
        commandInputRef.current?.focus();
      }, 50);
      return;
    }

    // Handle Spotify control commands directly - DON'T close the window
    // This keeps the launcher open so users can see the Spotify player update
      if (command.handler_type === "spotify_control" && command.endpoint) {
      try {
        const response = await fetch(`${baseUrl}${command.endpoint}`, {
          method: 'POST'
        });

        if (!response.ok) {
          console.error(`Spotify control failed: ${command.id}`);
        }
        // Don't close - keep launcher open for Spotify interaction
        return;
      } catch (error) {
        console.error('Spotify control error:', error);
        return;
      }
    }

    // DON'T close the window - Raycast-style behavior keeps it open
    // Show response and orchestration animations in the launcher

    // Handle slash commands - send via WebSocket for orchestration visibility
      if (command.handler_type === "slash_command") {
        const slashMessage = argument 
          ? `/${command.id} ${argument}`
          : `/${command.id}`;
        
      logger.info("[LAUNCHER] Executing slash command via WebSocket", { command: command.id, message: slashMessage });
      setIsProcessing(true);
      setCurrentResponse("");
      wsSendMessage(slashMessage);
      
      // Reset view state but DON'T close
        setViewState("search");
        setSelectedCommand(null);
        setCommandArg("");
        return;
      }

    // Send agent commands via WebSocket for orchestration visibility
    const message = query.trim() || `Execute ${command.title}`;
    logger.info("[LAUNCHER] Executing agent command via WebSocket", { command: command.id, message });
    setIsProcessing(true);
    setCurrentResponse("");
    wsSendMessage(message);
    
  }, [query, baseUrl, viewState, wsSendMessage]);

  // Handle command argument submission
  const handleCommandArgSubmit = useCallback(() => {
    if (selectedCommand) {
      handleExecuteCommand(selectedCommand, commandArg);
    }
  }, [selectedCommand, commandArg, handleExecuteCommand]);

  // Handle keyboard navigation in command input view
  useEffect(() => {
    if (viewState !== "command_input") return;

    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleCommandArgSubmit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        setViewState("search");
        setSelectedCommand(null);
        setCommandArg("");
        // Refocus search input
        setTimeout(() => {
          inputRef.current?.focus();
        }, 50);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [viewState, handleCommandArgSubmit]);

  // Debounced search - use ref instead of state to avoid infinite loop
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(
        `${baseUrl}/api/universal-search?q=${encodeURIComponent(searchQuery)}&limit=10`
      );

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status}`);
      }

      const data = await response.json();
      setResults(data.results || []);
      setSelectedIndex(0);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl]);

  // Debounced search effect - only trigger for file commands or overlay mode
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Only trigger file search for:
    // 1. Overlay mode (file browser)
    // 2. Explicit file commands (/file, /folder, /files)
    const isFileCommand = query.startsWith('/file') || query.startsWith('/folder') || query.startsWith('/files');
    
    const slashCommandActive = query.startsWith('/');

    const shouldSearch = (() => {
      if (mode === "overlay") {
        if (slashCommandActive && !isFileCommand) {
          logger.debug("[COMMAND PALETTE] Suppressing semantic search for slash command", { query });
          return false;
        }
        return true;
      }
      return isFileCommand;
    })();

    if (shouldSearch) {
      const timer = setTimeout(() => {
        // Strip the command prefix for file searches
        const searchQuery = isFileCommand 
          ? query.replace(/^\/(file|folder|files)\s*/, '').trim()
          : query;
        performSearch(searchQuery || query); // Use original if stripped is empty
      }, 200);

      debounceTimerRef.current = timer;
    } else {
      // Clear file results for regular chat queries when search is suppressed
      setResults([]);
    }

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [mode, performSearch, query]); // Added mode to deps

  // Fetch commands on mount
  useEffect(() => {
    const fetchCommands = async () => {
      try {
        const response = await fetch(`${baseUrl}/api/commands`);
        if (response.ok) {
          const data = await response.json();
          setCommands(data.commands || []);
          logger.info("[COMMAND PALETTE] Commands loaded", { count: data.commands?.length });
        }
      } catch (error) {
        console.error('Error fetching commands:', error);
      }
    };

    fetchCommands();
  }, [baseUrl]);

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setQuery(initialQuery);
      setResults([]);
      setSelectedIndex(0);
      setPreviewMode('closed');
      setPreviewData(null);
      setIsLoading(false);
      setShowingResults("both");
      logger.info("[COMMAND PALETTE] Opened", { source, initialQuery });
      // Pass the input ref to parent when mounting
      if (onMount && inputRef.current) {
        onMount(inputRef.current);
      }
    }
  }, [isOpen, initialQuery, onMount, source]);

  // Load mini conversation depth from settings whenever the launcher opens
  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (!isElectron()) {
      setMiniConversationTurns(DEFAULT_MINI_CONVO_TURNS);
      return;
    }

    let isCancelled = false;

    const loadMiniConversationDepth = async () => {
      try {
        const loaded = await window.electronAPI?.getSettings();
        if (!loaded || isCancelled) return;
        setMiniConversationTurns(
          clampMiniConversationDepth(
            loaded.miniConversationDepth ?? DEFAULT_MINI_CONVO_TURNS
          )
        );
      } catch (error) {
        logger.error("[COMMAND PALETTE] Failed to load mini conversation depth", { error });
        setMiniConversationTurns(DEFAULT_MINI_CONVO_TURNS);
      }
    };

    loadMiniConversationDepth();

    return () => {
      isCancelled = true;
    };
  }, [isOpen]);

  // Detect if user is typing a slash command
  const isSlashMode = query.startsWith('/');
  const slashQuery = isSlashMode ? query.slice(1).toLowerCase() : '';

  // Filter commands based on query - prioritize slash commands when typing /
  const filteredCommands = useMemo(() => {
    if (!query.trim()) {
      // Show top 5 when no query, but exclude spotify_control commands
      return commands.filter(cmd => cmd.handler_type !== 'spotify_control').slice(0, 5);
    }

    // Slash command mode: show only slash commands that match
    if (isSlashMode) {
      const slashCommands = commands.filter(cmd => cmd.handler_type === "slash_command");
      if (!slashQuery) {
        // Just "/" typed - show all slash commands
        return slashCommands;
      }
      // Filter by the text after "/"
      return slashCommands.filter(cmd =>
        cmd.id.toLowerCase().includes(slashQuery) ||
        cmd.title.toLowerCase().includes(slashQuery) ||
        cmd.keywords.some(kw => kw.toLowerCase().includes(slashQuery))
      );
    }

    const lowerQuery = query.toLowerCase();
    return commands.filter(cmd =>
      cmd.handler_type !== 'spotify_control' && ( // Exclude Spotify control commands
        cmd.title.toLowerCase().includes(lowerQuery) ||
        cmd.description.toLowerCase().includes(lowerQuery) ||
        cmd.keywords.some(kw => kw.toLowerCase().includes(lowerQuery)) ||
        cmd.category.toLowerCase().includes(lowerQuery)
      )
    );
  }, [query, commands, isSlashMode, slashQuery]);

  // Combined results for keyboard navigation
  const allItems = useMemo(() => {
    const items: Array<{ type: 'command' | 'file', data: Command | SearchResult }> = [];

    if (showingResults === "both" || showingResults === "commands") {
      filteredCommands.forEach(cmd => items.push({ type: 'command', data: cmd }));
    }

    if (showingResults === "both" || showingResults === "files") {
      results.forEach(result => items.push({ type: 'file', data: result }));
    }

    return items;
  }, [filteredCommands, results, showingResults]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        if (previewMode !== 'closed') {
          setPreviewMode('closed');
          setPreviewData(null);
        } else {
          onClose();
        }
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex(prev =>
          prev === allItems.length - 1 ? 0 : prev + 1
        );
        return;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(prev =>
          prev === 0 ? allItems.length - 1 : prev - 1
        );
        return;
      }

      if (e.key === "Enter") {
        // If focus is in the search input, let the input handler deal with it
        // This ensures queries are always submitted via WebSocket (Raycast-style)
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT') {
          // Input handler will submit via WebSocket
          return;
        }
        
        // Only execute file operations when NOT in input (e.g., preview focused)
        e.preventDefault();
        const selectedItem = allItems[selectedIndex];
        if (selectedItem && selectedItem.type === 'file') {
            const result = selectedItem.data as SearchResult;
            if (e.metaKey || e.ctrlKey) {
              handleOpenExternal(result);
            } else {
              handleSelectResult(result);
            }
          }
        // Commands are NOT executed on Enter anymore - they go through WebSocket
        return;
      }

      if (e.key === " ") {
        // Only toggle preview if NOT typing in the search input
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
          // Allow space to be typed in input fields
          return;
        }
        e.preventDefault();
        const selectedItem = allItems[selectedIndex];
        if (selectedItem && selectedItem.type === 'file') {
          togglePreview(selectedItem.data as SearchResult);
        }
        return;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, allItems, selectedIndex, previewMode, onClose, handleOpenExternal, handleSelectResult, handleExecuteCommand, togglePreview]);

  const getFileIcon = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case 'pdf':
        return '📄';
      case 'docx':
      case 'doc':
        return '📝';
      case 'txt':
        return '📃';
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
      case 'webp':
        return '🖼️';
      default:
        return '📄';
    }
  };

  // Always render SettingsModal even when palette is closed
  const settingsModalElement = (
    <SettingsModal 
      isOpen={showSettings} 
      onClose={() => setShowSettings(false)} 
    />
  );

  const slackTemplates = [
    { label: "Summarize #backend (24h)", value: "summarize #backend last 24 hours" },
    { label: "Decisions about onboarding", value: "decisions about onboarding flow this week" },
    { label: "Tasks from #incidents (yesterday)", value: "tasks #incidents yesterday" },
    { label: "Topic: billing_service", value: "topic billing_service last 14d" },
    { label: "Summarize thread link", value: "summarize https://slack.com/archives/C123/p1234567890123456" },
  ];

  const renderSlackHintPanel = () => {
    if (selectedCommand?.id !== "slack") return null;
    return (
      <div className="mt-4 space-y-2 rounded-xl border border-glass/40 bg-glass/20 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Slack templates
        </div>
        <div className="flex flex-wrap gap-2">
          {slackTemplates.map((template) => (
            <button
              key={template.label}
              onClick={() => setCommandArg(template.value)}
              className="rounded-full border border-glass/40 px-3 py-1 text-xs font-medium text-text-muted hover:border-accent-primary/40 hover:text-accent-primary"
              type="button"
            >
              {template.label}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-text-muted/80">
          Tip: Mention #channel names, add time windows like &ldquo;last week&rdquo;, include keywords (`decisions`, `tasks`), or paste a Slack thread link.
        </p>
      </div>
    );
  };

  if (!isOpen) return settingsModalElement;

  if (mode === "launcher") {
    // Launcher mode: full window, embedded Spotify
    return (
      <>
      {settingsModalElement}
      <div className="h-screen w-full flex flex-col bg-gradient-to-br from-neutral-900 via-neutral-800 to-neutral-900">
        <div className="flex-1 flex items-center justify-center px-8 py-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
            className="w-full max-w-4xl flex"
            data-testid="command-palette"
          >
            {/* Command Input View */}
            {viewState === "command_input" && selectedCommand ? (
              <div className="flex-1 bg-glass-elevated backdrop-blur-glass rounded-2xl border border-glass shadow-elevated shadow-inset-border overflow-hidden flex flex-col">
                {/* Header with back button */}
                <div className="p-4 border-b border-glass/30 flex items-center gap-3">
                  <button
                    onClick={() => {
                      setViewState("search");
                      setSelectedCommand(null);
                      setCommandArg("");
                      setTimeout(() => inputRef.current?.focus(), 50);
                    }}
                    className="p-1.5 rounded-lg hover:bg-glass-hover transition-colors text-text-muted hover:text-text-primary"
                    title="Back to search"
                  >
                    <span className="text-lg">←</span>
                  </button>
                  <div className="text-xl">{selectedCommand.icon}</div>
                  <div className="flex-1">
                    <div className="text-sm font-medium text-text-primary">{selectedCommand.title}</div>
                    <div className="text-xs text-text-muted">{selectedCommand.description}</div>
                  </div>
                </div>

                {/* Command Argument Input */}
                <div className="flex-1 flex flex-col p-4">
                  <input
                    ref={commandInputRef}
                    type="text"
                    value={commandArg}
                    onChange={(e) => setCommandArg(e.target.value)}
                    placeholder={selectedCommand.placeholder || "Enter argument..."}
                    className="flex-1 bg-transparent text-text-primary placeholder-text-muted outline-none text-lg font-medium"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleCommandArgSubmit();
                      }
                    }}
                  />
                  {renderSlackHintPanel()}
                  
                  {/* Keyboard hints */}
                  <div className="mt-4 pt-4 border-t border-glass/30">
                    <div className="flex items-center justify-between text-xs text-text-muted">
                      <div className="flex items-center gap-4">
                        <span>↵ Execute</span>
                        <span>Esc Back</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* Main Search Panel */
              <div className={cn(
                "flex-1 bg-glass-elevated backdrop-blur-glass rounded-2xl",
                "border border-glass shadow-elevated shadow-inset-border",
                "overflow-hidden flex flex-col",
                previewMode !== 'closed' ? 'rounded-r-none' : ''
              )}>
                {/* Search Input with Raycast-style polish */}
                <div className="p-4 border-b border-glass/30">
                  <div className="flex items-center gap-3">
                    <div className="text-lg">🔍</div>
                    <input
                      ref={inputRef}
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={(e) => {
                        // Handle Tab to autocomplete slash command
                        if (e.key === "Tab" && isSlashMode && filteredCommands.length > 0) {
                          e.preventDefault();
                          const firstCmd = filteredCommands[0];
                          setQuery(`/${firstCmd.id} `);
                          return;
                        }
                        // Handle Enter key
                        if (e.key === "Enter" && query.trim()) {
                          e.preventDefault();
                          e.stopPropagation();
                          
                          // If it's a calculation, copy the result to clipboard
                          if (isCalculation(query)) {
                            const raw = getRawResult(query);
                            if (raw) {
                              navigator.clipboard.writeText(raw);
                              setCurrentResponse("📋 Copied to clipboard!");
                              setTimeout(() => setCurrentResponse(""), 2000);
                              logger.info("[LAUNCHER] Calculator result copied", { result: raw });
                              return;
                            }
                          }
                          
                          // Otherwise submit via WebSocket - Raycast-style behavior
                          logger.info("[LAUNCHER] Enter pressed - submitting query", { query: query.trim() });
                          handleSubmitQuery();
                        }
                      }}
                      placeholder={source === "folder" ? "Search folders and files..." : "Type / for commands or ask anything..."}
                      className="flex-1 bg-transparent text-text-primary placeholder-text-muted outline-none text-lg font-medium"
                      autoFocus
                      data-testid="command-palette-query"
                    />
                    {isLoading && (
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                        className="w-5 h-5 border-2 border-accent-primary border-t-transparent rounded-full"
                      />
                    )}
                    {/* Voice Recording Button */}
                    <motion.button
                      onClick={handleVoiceRecord}
                      disabled={isTranscribing}
                      className={cn(
                        "relative p-2 rounded-lg transition-all duration-200",
                        isRecording
                          ? "bg-red-500/20 text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.3)]"
                          : isTranscribing
                          ? "bg-accent-primary/20 text-accent-primary cursor-wait"
                          : "text-text-muted hover:text-text-primary hover:bg-glass-hover"
                      )}
                      title={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Voice input"}
                      whileHover={!isRecording && !isTranscribing ? { scale: 1.05 } : {}}
                      whileTap={!isTranscribing ? { scale: 0.95 } : {}}
                      animate={isRecording ? {
                        scale: [1, 1.1, 1],
                        transition: { duration: 1.5, repeat: Infinity, ease: "easeInOut" }
                      } : {}}
                    >
                      {isTranscribing ? (
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                          className="w-5 h-5 border-2 border-accent-primary border-t-transparent rounded-full"
                        />
                      ) : (
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                      )}
                      {/* Pulsing ring when recording */}
                      {isRecording && (
                        <>
                          <motion.span
                            className="absolute inset-0 rounded-lg border-2 border-red-400"
                            animate={{ scale: [1, 1.3, 1], opacity: [0.8, 0, 0.8] }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
                          />
                          <motion.span
                            className="absolute inset-0 rounded-lg border-2 border-red-400"
                            animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut", delay: 0.3 }}
                          />
                        </>
                      )}
                    </motion.button>
                    {/* Expand Button - opens ChatGPT-style desktop window */}
                    <motion.button
                      onClick={() => {
                        logger.info("[LAUNCHER] Expand button clicked");
                        openExpandedWindow();
                      }}
                      className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-glass-hover transition-all"
                      title="Expand to full window (ChatGPT-style)"
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                      </svg>
                    </motion.button>
                  </div>
                </div>

                {/* Spotify Mini Player - portrait card widget (Raycast-style) */}
                <div className="px-4 pt-3 pb-3">
                  <SpotifyMiniPlayer variant="launcher-mini" />
                </div>

                {/* Response Area - shows immediately below Spotify when processing or has response */}
                <AnimatePresence>
                  {(isProcessing || currentResponse || planState) && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="border-b border-glass/30 bg-gradient-to-b from-glass/30 to-glass/10"
                    >
                      {/* Plan Progress Rail - shows orchestration steps (planning or executing) */}
                      {planState && (planState.status === "executing" || planState.status === "planning") && (
                        <div className="px-4 py-3 border-b border-glass/20">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-medium text-accent-primary uppercase tracking-wide">
                              {planState.status === "planning" ? "🧠 Planning..." : "🎯 Executing Plan"}
                            </span>
                            {planState.steps.length > 0 && (
                              <span className="text-xs text-text-muted">
                                {planState.steps.filter(s => s.status === "completed").length}/{planState.steps.length} steps
                              </span>
                            )}
                          </div>
                          {/* Inline step indicators */}
                          <div className="flex items-center gap-1 flex-wrap">
                            {planState.steps.map((step, idx) => (
                              <motion.div
                                key={step.id}
                                className={cn(
                                  "flex items-center gap-1.5 px-2 py-1 rounded-md text-xs",
                                  step.status === "running" && "bg-accent-primary/20 text-accent-primary border border-accent-primary/40",
                                  step.status === "completed" && "bg-green-500/20 text-green-400",
                                  step.status === "failed" && "bg-red-500/20 text-red-400",
                                  step.status === "pending" && "bg-glass/30 text-text-muted"
                                )}
                                animate={step.status === "running" ? {
                                  boxShadow: ["0 0 0px rgba(59,130,246,0)", "0 0 10px rgba(59,130,246,0.5)", "0 0 0px rgba(59,130,246,0)"]
                                } : {}}
                                transition={{ duration: 1.5, repeat: Infinity }}
                              >
                                {step.status === "running" && (
                                  <motion.span
                                    animate={{ rotate: 360 }}
                                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                                  >
                                    ⚙️
                                  </motion.span>
                                )}
                                {step.status === "completed" && <span>✓</span>}
                                {step.status === "failed" && <span>✗</span>}
                                {step.status === "pending" && <span className="opacity-50">○</span>}
                                <span className="truncate max-w-24">{step.action}</span>
                              </motion.div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="px-4 py-2 text-xs font-medium text-text-muted uppercase tracking-wide flex items-center gap-2">
                        <span>🤖</span>
                        <span>Response</span>
                        {isProcessing && (
                          <motion.span
                            animate={{ opacity: [0.5, 1, 0.5] }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                            className="text-accent-primary"
                          >
                            processing...
                          </motion.span>
                        )}
                      </div>
                      <div className="px-4 pb-3 max-h-48 overflow-y-auto">
                        {/* Show what was submitted */}
                        {submittedQuery && (
                          <div className="mb-2 pb-2 border-b border-glass/20">
                            <span className="text-xs text-text-muted">Query: </span>
                            <span className="text-sm text-text-secondary">{submittedQuery}</span>
                          </div>
                        )}
                        
                        {isProcessing && !currentResponse ? (
                          <div className="flex items-center gap-2 py-2">
                            <TypingIndicator />
                            <span className="text-sm text-text-muted animate-pulse">Thinking...</span>
                          </div>
                        ) : currentResponse ? (
                          <div className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
                            {currentResponse}
                          </div>
                        ) : null}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

              {/* Results List - scrollable (only shows when relevant) */}
              <div className="flex-1 overflow-y-auto min-h-0">
                {/* Quick Calculator Result */}
                {isCalculation(query) && evaluateCalculation(query) && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="px-4 py-3 border-b border-glass/30 bg-gradient-to-r from-accent-primary/10 to-transparent"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">🧮</span>
                        <div>
                          <div className="text-2xl font-mono text-text-primary font-semibold">
                            {evaluateCalculation(query)}
                          </div>
                          <div className="text-xs text-text-muted font-mono">
                            = {query}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            const raw = getRawResult(query);
                            if (raw) {
                              navigator.clipboard.writeText(raw);
                              setCurrentResponse("Copied to clipboard!");
                              setTimeout(() => setCurrentResponse(""), 2000);
                            }
                          }}
                          className="px-3 py-1.5 text-xs bg-accent-primary/20 hover:bg-accent-primary/30 text-accent-primary rounded-lg transition-colors"
                        >
                          Copy
                        </button>
                        <span className="text-xs text-text-muted">↵ to copy</span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {allItems.length === 0 && !isLoading && query && !isSlashMode && !isCalculation(query) && (
                  <div className="p-8 text-center text-text-muted">
                    <div className="text-4xl mb-2">📭</div>
                    <p>No results match &quot;{query}&quot;</p>
                    <p className="text-sm mt-1">Try different keywords</p>
                  </div>
                )}

                {/* Slash Command Autocomplete Dropdown */}
                {isSlashMode && filteredCommands.length > 0 && (
                  <div className="border-b border-glass/30">
                    <div className="px-4 py-2 text-xs font-medium text-accent-primary uppercase tracking-wide flex items-center gap-2">
                      <span>/</span>
                      <span>Commands</span>
                      <span className="text-text-muted ml-auto">Tab to complete</span>
                    </div>
                    {filteredCommands.map((command, cmdIndex) => {
                      const globalIndex = allItems.findIndex(
                        item => item.type === 'command' && (item.data as Command).id === command.id
                      );
                      return (
                        <motion.button
                          key={command.id}
                          onClick={() => {
                            // Insert the command into input
                            setQuery(`/${command.id} `);
                            inputRef.current?.focus();
                          }}
                          onMouseEnter={() => setSelectedIndex(globalIndex)}
                          whileHover={{ scale: 1.01 }}
                          whileTap={{ scale: 0.99 }}
                          className={cn(
                            "w-full text-left p-3 border-b border-glass/30 transition-colors flex items-center gap-3",
                            globalIndex === selectedIndex
                              ? "bg-accent-primary/10 border-l-2 border-l-accent-primary"
                              : "hover:bg-glass-hover/50"
                          )}
                        >
                          <span className="text-lg">{command.icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-accent-primary">/{command.id}</span>
                              <span className="text-sm text-text-primary">{command.title}</span>
                            </div>
                            <div className="text-xs text-text-muted truncate">{command.description}</div>
                          </div>
                          {command.command_type === "with_input" && (
                            <span className="text-xs text-text-muted bg-glass/30 px-2 py-0.5 rounded">+ args</span>
                          )}
                        </motion.button>
                      );
                    })}
                  </div>
                )}

                {/* Slash mode - no commands found */}
                {isSlashMode && filteredCommands.length === 0 && slashQuery && (
                  <div className="p-6 text-center text-text-muted">
                    <div className="text-2xl mb-2">🔍</div>
                    <p>No command matches &quot;/{slashQuery}&quot;</p>
                    <p className="text-sm mt-1">Try /bluesky, /calendar, /files, etc.</p>
                  </div>
                )}

                {/* Show commands section (non-slash mode) - Raycast-style Actions */}
                {!isSlashMode && filteredCommands.length > 0 && (
                  <div className="border-b border-glass/30">
                    <div className="px-4 py-2 text-xs font-semibold text-accent-primary/80 uppercase tracking-wider flex items-center gap-2">
                      <span>⚡</span>
                      <span>Actions</span>
                      <span className="text-text-muted font-normal ml-auto">{filteredCommands.length}</span>
                    </div>
                    {filteredCommands.slice(0, 6).map((command, cmdIndex) => {
                      const globalIndex = allItems.findIndex(
                        item => item.type === 'command' && (item.data as Command).id === command.id
                      );
                      return (
                        <CommandItem
                          key={command.id}
                          command={command}
                          isSelected={globalIndex === selectedIndex}
                          onClick={() => handleExecuteCommand(command)}
                          onMouseEnter={() => setSelectedIndex(globalIndex)}
                        />
                      );
                    })}
                  </div>
                )}

                {/* Show files section - always show header when there are files */}
                {results.length > 0 && (
                  <div>
                    <div className="px-4 py-2 text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-2">
                      <span>📄</span>
                      <span>Files</span>
                      <span className="font-normal ml-auto">{results.length}</span>
                    </div>
                    {results.map((result, fileIndex) => {
                      const globalIndex = allItems.findIndex(
                        item => item.type === 'file' && (item.data as SearchResult).file_path === result.file_path
                      );
                      return (
                        <SearchResultItem
                          key={result.file_path}
                          result={result}
                          isSelected={globalIndex === selectedIndex}
                          onClick={() => handleSelectResult(result)}
                          onMouseEnter={() => setSelectedIndex(globalIndex)}
                          onPreviewToggle={() => togglePreview(result)}
                          getFileIcon={getFileIcon}
                          dataTestId={`files-result-item-${fileIndex}`}
                        />
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Conversation History Panel */}
              {chatMessages.length > 0 && (
                <LauncherHistoryPanel
                  messages={chatMessages}
                  planState={planState}
                  isProcessing={isProcessing}
                  maxHeight={150}
                  maxTurns={miniConversationTurns}
                  onExpand={() => {
                    logger.info("[LAUNCHER] Expand to desktop view requested");
                    openExpandedWindow();
                  }}
                />
              )}

              {/* Footer with keyboard hints */}
              <div className="p-3 border-t border-glass bg-glass-elevated/50">
                <div className="flex items-center justify-between text-xs text-text-muted">
                  <div className="flex items-center gap-4">
                    <span>↑↓ Navigate</span>
                    <span>↵ Submit</span>
                    <span>Esc Close</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>⌘+Option+K</span>
                  </div>
                </div>
              </div>
            </div>
            )}

            {/* Preview Panel - only show in search view */}
            {viewState === "search" && (
              <AnimatePresence>
                {previewMode !== 'closed' && previewData && (
                  <motion.div
                    initial={{ opacity: 0, x: 20, width: 0 }}
                    animate={{ opacity: 1, x: 0, width: 400 }}
                    exit={{ opacity: 0, x: 20, width: 0 }}
                    transition={{ duration: 0.2 }}
                    className="bg-glass-elevated backdrop-blur-glass rounded-r-2xl border border-glass border-l-0 shadow-elevated overflow-hidden"
                    data-testid="files-preview-pane"
                  >
                    <DocumentPreview
                      result={previewData}
                      mode={previewMode}
                      onClose={() => {
                        setPreviewMode('closed');
                        setPreviewData(null);
                      }}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            )}
          </motion.div>
        </div>

        {/* Voice Recording Overlay */}
        <RecordingIndicator
          isRecording={isRecording}
          isTranscribing={isTranscribing}
          onStop={handleStopRecording}
          error={voiceError || voiceRecorderError}
          onRetry={() => {
            setVoiceError(null);
            handleVoiceRecord();
          }}
          onCancel={() => {
            setVoiceError(null);
          }}
        />
      </div>
      </>
    );
  }

  // Overlay mode (original behavior)
  return (
    <>
    {settingsModalElement}
    <AnimatePresence>
      <motion.div
        initial="hidden"
        animate="visible"
        exit="hidden"
        variants={overlayFade}
        className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4"
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            onClose();
          }
        }}
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

        {/* Modal Container */}
        <motion.div
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={modalSlideDown}
          className="relative w-full max-w-4xl max-h-[80vh] flex"
          onClick={(e) => e.stopPropagation()}
          data-testid="command-palette"
        >
          {/* Command Input View */}
          {viewState === "command_input" && selectedCommand ? (
            <div className="flex-1 bg-glass-elevated backdrop-blur-glass rounded-2xl border border-glass shadow-elevated shadow-inset-border overflow-hidden flex flex-col">
              {/* Header with back button */}
              <div className="p-4 border-b border-glass/30 flex items-center gap-3">
                <button
                  onClick={() => {
                    setViewState("search");
                    setSelectedCommand(null);
                    setCommandArg("");
                    setTimeout(() => inputRef.current?.focus(), 50);
                  }}
                  className="p-1.5 rounded-lg hover:bg-glass-hover transition-colors text-text-muted hover:text-text-primary"
                  title="Back to search"
                >
                  <span className="text-lg">←</span>
                </button>
                <div className="text-xl">{selectedCommand.icon}</div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-text-primary">{selectedCommand.title}</div>
                  <div className="text-xs text-text-muted">{selectedCommand.description}</div>
                </div>
              </div>

              {/* Command Argument Input */}
              <div className="flex-1 flex flex-col p-4">
                <input
                  ref={commandInputRef}
                  type="text"
                  value={commandArg}
                  onChange={(e) => setCommandArg(e.target.value)}
                  placeholder={selectedCommand.placeholder || "Enter argument..."}
                  className="flex-1 bg-transparent text-text-primary placeholder-text-muted outline-none text-lg font-medium"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleCommandArgSubmit();
                    }
                  }}
                />
                {renderSlackHintPanel()}
                
                {/* Keyboard hints */}
                <div className="mt-4 pt-4 border-t border-glass/30">
                  <div className="flex items-center justify-between text-xs text-text-muted">
                    <div className="flex items-center gap-4">
                      <span>↵ Execute</span>
                      <span>Esc Back</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Main Search Panel */
            <div className={cn(
              "flex-1 bg-glass-elevated backdrop-blur-glass rounded-2xl",
              "border border-glass shadow-elevated shadow-inset-border",
              "overflow-hidden",
              previewMode !== 'closed' ? 'rounded-r-none' : ''
            )}>
              {/* Search Input */}
              <div className="p-4 border-b border-glass">
                <div className="flex items-center gap-3">
                  <div className="text-lg">🔍</div>
                  <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={source === "folder" ? "Search folders and files..." : "Search documents..."}
                    className="flex-1 bg-transparent text-text-primary placeholder-text-muted outline-none text-lg"
                    autoFocus
                    data-testid="command-palette-query"
                  />
                  {isLoading && (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      className="w-5 h-5 border-2 border-accent-primary border-t-transparent rounded-full"
                    />
                  )}
                </div>
              </div>

            {/* Results List */}
            <div className="max-h-96 overflow-y-auto">
              {/* Quick Calculator Result (Overlay mode) */}
              {isCalculation(query) && evaluateCalculation(query) && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="px-4 py-3 border-b border-glass/30 bg-gradient-to-r from-accent-primary/10 to-transparent"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">🧮</span>
                      <div>
                        <div className="text-2xl font-mono text-text-primary font-semibold">
                          {evaluateCalculation(query)}
                        </div>
                        <div className="text-xs text-text-muted font-mono">
                          = {query}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          const raw = getRawResult(query);
                          if (raw) {
                            navigator.clipboard.writeText(raw);
                          }
                        }}
                        className="px-3 py-1.5 text-xs bg-accent-primary/20 hover:bg-accent-primary/30 text-accent-primary rounded-lg transition-colors"
                      >
                        Copy
                      </button>
                      <span className="text-xs text-text-muted">↵ to copy</span>
                    </div>
                  </div>
                </motion.div>
              )}

              {allItems.length === 0 && !isLoading && query && !isCalculation(query) && (
                <div className="p-8 text-center text-text-muted">
                  <div className="text-4xl mb-2">📭</div>
                  <p>No results match &quot;{query}&quot;</p>
                  <p className="text-sm mt-1">Try different keywords</p>
                </div>
              )}

              {/* Show commands section */}
              {filteredCommands.length > 0 && (
                <div className="border-b border-glass/30">
                  <div className="px-4 py-2 text-xs font-medium text-text-muted uppercase tracking-wide">
                    Actions
                  </div>
                  {filteredCommands.map((command, cmdIndex) => {
                    const globalIndex = allItems.findIndex(
                      item => item.type === 'command' && (item.data as Command).id === command.id
                    );
                    return (
                      <CommandItem
                        key={command.id}
                        command={command}
                        isSelected={globalIndex === selectedIndex}
                        onClick={() => handleExecuteCommand(command)}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                      />
                    );
                  })}
                </div>
              )}

              {/* Show files section */}
              {results.length > 0 && (
                <div>
                  {filteredCommands.length > 0 && (
                    <div className="px-4 py-2 text-xs font-medium text-text-muted uppercase tracking-wide">
                      Files
                    </div>
                  )}
                  {results.map((result, fileIndex) => {
                    const globalIndex = allItems.findIndex(
                      item => item.type === 'file' && (item.data as SearchResult).file_path === result.file_path
                    );
                    return (
                      <SearchResultItem
                        key={result.file_path}
                        result={result}
                        isSelected={globalIndex === selectedIndex}
                        onClick={() => handleSelectResult(result)}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                        onPreviewToggle={() => togglePreview(result)}
                        getFileIcon={getFileIcon}
                        dataTestId={`files-result-item-${fileIndex}`}
                      />
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-3 border-t border-glass bg-glass-elevated/50">
              <div className="flex items-center justify-between text-xs text-text-muted">
                <div className="flex items-center gap-4">
                  <span>↑↓ Navigate</span>
                  <span>↵ Open in App</span>
                  <span>␣ Preview</span>
                  <span>⌘↵ Open External</span>
                </div>
                <div>Esc to close</div>
              </div>
            </div>
          </div>
          )}

          {/* Preview Panel - only show in search view */}
          {viewState === "search" && (
            <AnimatePresence>
              {previewMode !== 'closed' && previewData && (
              <motion.div
                initial={{ opacity: 0, x: 20, width: 0 }}
                animate={{ opacity: 1, x: 0, width: 400 }}
                exit={{ opacity: 0, x: 20, width: 0 }}
                transition={{ duration: 0.2 }}
                className="bg-glass-elevated backdrop-blur-glass rounded-r-2xl border border-glass border-l-0 shadow-elevated overflow-hidden"
                data-testid="files-preview-pane"
              >
                <DocumentPreview
                  result={previewData}
                  mode={previewMode}
                  onClose={() => {
                    setPreviewMode('closed');
                    setPreviewData(null);
                  }}
                />
              </motion.div>
            )}
          </AnimatePresence>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
    </>
  );
}

interface SearchResultItemProps {
  result: SearchResult;
  isSelected: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onPreviewToggle: () => void;
  getFileIcon: (fileType: string) => string;
  dataTestId?: string;
}

function SearchResultItem({
  result,
  isSelected,
  onClick,
  onMouseEnter,
  onPreviewToggle,
  getFileIcon,
  dataTestId
}: SearchResultItemProps) {
  return (
    <motion.button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      className={cn(
        "w-full text-left p-4 border-b border-glass/50 transition-colors",
        isSelected
          ? "bg-glass-hover shadow-inset-border"
          : "hover:bg-glass-hover/50"
      )}
      data-testid={dataTestId || "files-result-item"}
    >
      <div className="flex items-start gap-3">
        {/* File Icon or Thumbnail */}
        <div className="w-8 h-8 mt-1 flex-shrink-0 flex items-center justify-center">
          {result.result_type === "image" && result.thumbnail_url ? (
            <img
              src={getApiBaseUrl() + result.thumbnail_url}
              alt={result.file_name}
              className="w-full h-full object-cover rounded border border-glass"
              onError={(e) => {
                // Fallback to icon if thumbnail fails
                e.currentTarget.style.display = 'none';
                e.currentTarget.parentElement!.innerHTML = getFileIcon(result.file_type);
              }}
            />
          ) : (
            <div className="text-2xl">{getFileIcon(result.file_type)}</div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* File Name and Type */}
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-text-primary truncate">
              {result.file_name}
            </h3>
            <span className="text-xs text-text-muted uppercase px-2 py-0.5 bg-glass rounded">
              {result.file_type}
            </span>
            {result.page_number && (
              <span className="text-xs text-text-muted px-2 py-0.5 bg-accent-primary/10 rounded">
                Page {result.page_number}
              </span>
            )}
          </div>

          {/* Breadcrumb */}
          <div className="text-sm text-text-muted mb-2 truncate">
            {result.breadcrumb}
          </div>

          {/* Snippet with Highlights */}
          <div className="text-sm text-text-primary leading-relaxed">
            <HighlightedText
              text={result.snippet}
              highlights={result.highlight_offsets}
            />
          </div>

          {/* Similarity Score */}
          <div className="text-xs text-text-muted mt-2">
            Match: {(result.similarity_score * 100).toFixed(1)}%
          </div>
        </div>

        {/* Preview Toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPreviewToggle();
          }}
          className="flex-shrink-0 p-2 text-text-muted hover:text-text-primary hover:bg-glass-hover rounded transition-colors"
          title="Quick preview (Space)"
        >
          👁️
        </button>
      </div>
    </motion.button>
  );
}

interface CommandItemProps {
  command: Command;
  isSelected: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
}

function CommandItem({
  command,
  isSelected,
  onClick,
  onMouseEnter
}: CommandItemProps) {
  return (
    <motion.button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      className={cn(
        "w-full text-left p-4 border-b border-glass/50 transition-colors",
        isSelected
          ? "bg-glass-hover shadow-inset-border"
          : "hover:bg-glass-hover/50"
      )}
      data-testid="command-item"
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="w-8 h-8 mt-1 flex-shrink-0 flex items-center justify-center text-2xl">
          {command.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title and Category */}
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-text-primary">
              {command.title}
            </h3>
            <span className="text-xs text-text-muted uppercase px-2 py-0.5 bg-glass rounded">
              {command.category}
            </span>
          </div>

          {/* Description */}
          <div className="text-sm text-text-muted">
            {command.description}
          </div>
        </div>

        {/* Action indicator */}
        <div className="flex-shrink-0 mt-1 text-text-muted text-xs">
          ↵
        </div>
      </div>
    </motion.button>
  );
}

interface HighlightedTextProps {
  text: string;
  highlights: [number, number][];
}

function HighlightedText({ text, highlights }: HighlightedTextProps) {
  if (!highlights || highlights.length === 0) {
    return <span>{text}</span>;
  }

  // Sort highlights by start position
  const sortedHighlights = [...highlights].sort((a, b) => a[0] - b[0]);

  const parts: { text: string; highlighted: boolean }[] = [];
  let lastEnd = 0;

  for (const [start, end] of sortedHighlights) {
    // Add non-highlighted text before this highlight
    if (start > lastEnd) {
      parts.push({
        text: text.slice(lastEnd, start),
        highlighted: false
      });
    }

    // Add highlighted text
    parts.push({
      text: text.slice(start, end),
      highlighted: true
    });

    lastEnd = end;
  }

  // Add remaining text
  if (lastEnd < text.length) {
    parts.push({
      text: text.slice(lastEnd),
      highlighted: false
    });
  }

  return (
    <>
      {parts.map((part, index) => (
        part.highlighted ? (
          <mark
            key={index}
            className="bg-accent-primary/20 text-accent-primary px-0.5 rounded"
          >
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        )
      ))}
    </>
  );
}

interface DocumentPreviewProps {
  result: SearchResult;
  mode: 'loading' | 'previewing';
  onClose: () => void;
}

function DocumentPreview({ result, mode, onClose }: DocumentPreviewProps) {
  const baseUrl = getApiBaseUrl();
  const [fileMetadata, setFileMetadata] = useState<{ size?: number; modified?: string } | null>(null);

  // Fetch file metadata
  useEffect(() => {
    if (mode === 'previewing' && result.file_path) {
      fetch(`${baseUrl}/api/files/metadata?path=${encodeURIComponent(result.file_path)}`)
        .then(res => res.json())
        .then(data => setFileMetadata(data))
        .catch(() => {
          // Silently fail - metadata is optional
        });
    }
  }, [mode, result.file_path, baseUrl]);

  const handleCopyPath = () => {
    navigator.clipboard.writeText(result.file_path);
    // Could show a toast here
  };

  const handleRevealInFinder = () => {
    if (isElectron()) {
      revealInFinder(result.file_path);
    } else {
      // Fallback: use API
      fetch(`${baseUrl}/api/reveal-file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: result.file_path }),
      }).catch(() => {});
    }
  };

  if (mode === 'loading') {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            className="w-8 h-8 border-2 border-accent-primary border-t-transparent rounded-full mx-auto mb-4"
          />
          <p className="text-text-muted">Loading preview...</p>
        </div>
      </div>
    );
  }

  const isImage = result.result_type === "image";
  const isPDF = result.file_type?.toLowerCase() === 'pdf';
  const previewUrl = `${baseUrl}/api/files/preview?path=${encodeURIComponent(result.file_path)}`;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-glass flex items-center justify-between">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-lg flex-shrink-0">{isImage ? '🖼️' : (isPDF ? '📄' : '📝')}</span>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-text-primary truncate" title={result.file_name}>
              {result.file_name}
            </h3>
            <p className="text-xs text-text-muted">
              {isImage ? (
                result.metadata?.width && result.metadata?.height ?
                  `${result.metadata.width} × ${result.metadata.height}px` :
                  'Image'
              ) : (
                result.page_number ? `Page ${result.page_number} of ${result.total_pages || 1}` : 'Document'
              )}
            </p>
            {fileMetadata && (
              <p className="text-xs text-text-muted mt-1">
                {fileMetadata.size && `${(fileMetadata.size / 1024).toFixed(1)} KB`}
                {fileMetadata.modified && ` • Modified: ${new Date(fileMetadata.modified).toLocaleDateString()}`}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary transition-colors p-1 rounded hover:bg-glass-hover flex-shrink-0"
          title="Close preview"
        >
          ✕
        </button>
      </div>

      {/* Preview Content */}
      <div className="flex-1 p-4 overflow-y-auto">
        {isImage ? (
          <div className="flex flex-col items-center justify-center h-full">
            {result.preview_url && (
              <img
                src={baseUrl + result.preview_url}
                alt={result.file_name}
                className="max-w-full max-h-full object-contain rounded-lg border border-glass shadow-lg"
                onError={(e) => {
                  // Fallback to thumbnail if preview fails
                  if (result.thumbnail_url) {
                    (e.target as HTMLImageElement).src = baseUrl + result.thumbnail_url;
                  }
                }}
              />
            )}
            {result.snippet && (
              <div className="text-center mt-4 max-w-md">
                <p className="text-sm text-text-primary mb-2">{result.snippet}</p>
                {result.metadata?.width && result.metadata?.height && (
                  <p className="text-xs text-text-muted">
                    {result.metadata.width} × {result.metadata.height} pixels
                  </p>
                )}
              </div>
            )}
          </div>
        ) : isPDF ? (
          <div className="h-full w-full">
            <iframe
              src={previewUrl}
              className="w-full h-full border-0 rounded-lg"
              title={result.file_name}
              onError={() => {
                // Fallback to snippet if PDF preview fails
              }}
            />
          </div>
        ) : (
          <div className="prose prose-sm max-w-none">
            <HighlightedText
              text={result.snippet}
              highlights={result.highlight_offsets}
            />
          </div>
        )}
      </div>

      {/* Footer with Actions */}
      <div className="p-3 border-t border-glass bg-glass-elevated/50">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span>Match: {(result.similarity_score * 100).toFixed(1)}%</span>
            {fileMetadata?.size && (
              <span>• {(fileMetadata.size / 1024).toFixed(1)} KB</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyPath}
              className="px-2 py-1 text-xs bg-glass hover:bg-glass-hover rounded transition-colors text-text-muted hover:text-text-primary"
              title="Copy file path"
            >
              Copy Path
            </button>
            <button
              onClick={handleRevealInFinder}
              className="px-2 py-1 text-xs bg-glass hover:bg-glass-hover rounded transition-colors text-text-muted hover:text-text-primary"
              title="Reveal in Finder"
            >
              Reveal
            </button>
            <span className="text-xs text-text-muted">↵ Open</span>
          </div>
        </div>
      </div>
    </div>
  );
}
