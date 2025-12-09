"use client";

import { useState, KeyboardEvent, useRef, useEffect, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { filterSlashCommands, getCommandsByScope, SlashCommandDefinition, getSlashQueryMetadata, normalizeSlashCommandInput } from "@/lib/slashCommands";
import { duration, easing } from "@/lib/motion";
import logger from "@/lib/logger";
import { useGlobalEventBus } from "@/lib/telemetry";
import { useSlashMetadataAutocomplete, AutocompleteSuggestion, AutocompleteRequest } from "@/lib/useSlashMetadataAutocomplete";
import { detectSlackContext, detectGitContext, detectYouTubeContext, replaceRange, getSuggestionToken, getSuggestionDescriptors } from "@/lib/slashMetadata";

interface InputAreaProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  onVoiceRecord?: () => void;
  isRecording?: boolean;
  initialValue?: string;
  onValueChange?: (value: string) => void;
  isProcessing?: boolean;
  onStop?: () => void;
}

export default function InputArea({
  onSend,
  disabled,
  initialValue = "",
  onValueChange,
  isProcessing = false,
  onStop,
  onVoiceRecord,
  isRecording = false,
}: InputAreaProps) {
  const [input, setInput] = useState(initialValue);
  const [inputCaret, setInputCaret] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);
  const eventBus = useGlobalEventBus();

  const slashMetadata = useMemo(() => getSlashQueryMetadata(input), [input]);
  const slashQuery = slashMetadata.commandToken;
  const showSlashPalette =
    input.startsWith("/") && !input.includes(" ") && !input.includes("\n");

  const filteredSlashCommands = useMemo(() => {
    if (!showSlashPalette) {
      return [];
    }
    return filterSlashCommands(slashQuery, "chat");
  }, [showSlashPalette, slashQuery]);

  const inputMetadataContext = useMemo(() => {
    if (!input.startsWith("/")) {
      return null;
    }
    const match = input.match(/^\/(\w+)\s+/);
    if (!match) {
      return null;
    }
    const commandId = match[1].toLowerCase();
    const argStart = match[0].length;
    const args = input.slice(argStart);
    const caretInArgs = Math.max(0, (inputCaret ?? input.length) - argStart);
    if (commandId === "slack") {
      const context = detectSlackContext(args, caretInArgs);
      if (!context) return null;
      return {
        ...context,
        range: [context.range[0] + argStart, context.range[1] + argStart] as [number, number],
      };
    }
    if (commandId === "git") {
      const context = detectGitContext(args, caretInArgs);
      if (!context) return null;
      return {
        ...context,
        range: [context.range[0] + argStart, context.range[1] + argStart] as [number, number],
      };
    }
    if (commandId === "youtube") {
      const context = detectYouTubeContext(args, caretInArgs);
      if (!context) return null;
      return {
        ...context,
        range: [context.range[0] + argStart, context.range[1] + argStart] as [number, number],
      };
    }
    return null;
  }, [input, inputCaret]);

  const inputMetadataRequest = useMemo<AutocompleteRequest | null>(() => {
    if (!inputMetadataContext) {
      return null;
    }
    switch (inputMetadataContext.kind) {
      case "slack-channel":
      case "slack-user":
        return {
          kind: inputMetadataContext.kind,
          query: inputMetadataContext.query,
        };
      case "git-repo":
        return {
          kind: "git-repo",
          query: inputMetadataContext.query,
        };
      case "git-branch":
        if (!inputMetadataContext.repoId) {
          return null;
        }
        return {
          kind: "git-branch",
          query: inputMetadataContext.query,
          repoId: inputMetadataContext.repoId,
        };
      case "youtube-video":
        return {
          kind: "youtube-video",
          query: inputMetadataContext.query,
        };
      default:
        return null;
    }
  }, [inputMetadataContext]);

  const {
    suggestions: metadataSuggestions,
    loading: metadataLoading,
    error: metadataError,
  } = useSlashMetadataAutocomplete(inputMetadataRequest, {
    enabled: Boolean(inputMetadataRequest),
  });
  const [metadataIndex, setMetadataIndex] = useState(0);
  useEffect(() => {
    setMetadataIndex(0);
  }, [metadataSuggestions.length, inputMetadataContext?.kind]);

  const showMetadataDropdown =
    Boolean(inputMetadataContext) &&
    (metadataSuggestions.length > 0 || metadataLoading || Boolean(metadataError));

  useEffect(() => {
    if (showSlashPalette) {
      setSelectedCommandIndex(0);
    }
  }, [showSlashPalette, filteredSlashCommands.length]);

  // Sync with external value changes
  // Use a ref to track if the change is from external source
  const isExternalChangeRef = useRef(false);

  useEffect(() => {
    // Only update if the external value is different and not empty
    // This prevents unnecessary re-renders and sync loops
    if (initialValue && initialValue !== input && !isExternalChangeRef.current) {
      isExternalChangeRef.current = true;
      setInput(initialValue);
      setInputCaret(initialValue.length);
      // Reset the flag after state update
      requestAnimationFrame(() => {
        isExternalChangeRef.current = false;
      });
    }
  }, [initialValue, input]);

  // Keyboard shortcuts (Raycast-style)
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      // Cmd+K or Ctrl+K to focus input
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        textareaRef.current?.focus();
      }
      // Cmd+L or Ctrl+L to clear input
      if ((e.metaKey || e.ctrlKey) && e.key === "l") {
        e.preventDefault();
        setInput("");
        textareaRef.current?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const updateInputCaret = useCallback(
    (target: HTMLTextAreaElement | null, fallbackValue?: string) => {
      if (!target) {
        const fallback = fallbackValue ?? input;
        setInputCaret(fallback.length);
        return;
      }
      setInputCaret(target.selectionStart ?? target.value.length);
    },
    [input],
  );

  const handleMetadataSelect = useCallback(
    (suggestion: AutocompleteSuggestion) => {
      if (!inputMetadataContext) {
        return;
      }
      const token = getSuggestionToken(suggestion);
      const next = replaceRange(input, inputMetadataContext.range, token, { appendSpace: true });
      setInput(next.value);
      setInputCaret(next.caret);
      onValueChange?.(next.value);
      requestAnimationFrame(() => {
        const textarea = textareaRef.current;
        if (textarea) {
          textarea.focus();
          textarea.setSelectionRange(next.caret, next.caret);
        }
      });
    },
    [inputMetadataContext, input, onValueChange],
  );

  const applySlashCommand = (command: SlashCommandDefinition) => {
    const newValue = `${command.command} `;
    setInput(newValue);
    setInputCaret(newValue.length);
    onValueChange?.(newValue);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      const target = textareaRef.current;
      if (target) {
        const cursorPos = newValue.length;
        target.setSelectionRange(cursorPos, cursorPos);
      }
    });
  };

  const handleSend = () => {
    if (isProcessing) {
      return;
    }

    // Handle /files as special UI command (opens palette, not chat)
    if (input.startsWith("/files")) {
      const query = input.replace(/^\/files\s*/, "");
      const trimmed = query.trim();
      if (trimmed.length > 0) {
        eventBus.emit("open-command-palette", { query: trimmed, source: "files" });
        logger.info("[INPUT] Opening command palette for /files search", { query: trimmed });
        // Emit telemetry for /files usage
        eventBus.emit("slash-command-used", { 
          command: "files", 
          invocation_source: "input_dropdown",
          query: trimmed 
        });
        setInput("");
        onValueChange?.("");
        return;
      }
    }

    // Handle /folder as special UI command for lookup mode (opens palette, not chat)
    // Only trigger palette for pure lookup queries (no organize/rename verbs)
    if (input.startsWith("/folder")) {
      const query = input.replace(/^\/folder\s*/, "");
      const trimmed = query.trim();
      
      // Check if this is a lookup query (not a management operation)
      const managementKeywords = ["organize", "rename", "normalize", "alpha", "sort", "arrange", "plan", "apply"];
      const isLookupQuery = trimmed.length > 0 && 
        !managementKeywords.some(keyword => trimmed.toLowerCase().includes(keyword));
      
      if (isLookupQuery) {
        eventBus.emit("open-command-palette", { query: trimmed, source: "folder" });
        logger.info("[COMMAND PALETTE] Opening command palette for /folder search", { query: trimmed });
        // Emit telemetry for /folder usage
        eventBus.emit("slash-command-used", { 
          command: "folder", 
          invocation_source: "input_dropdown",
          query: trimmed 
        });
        setInput("");
        onValueChange?.("");
        return;
      }
      // If it's a management operation, fall through to normal chat flow
    }

    // Check if this is a slash command and emit telemetry
    const trimmedInput = input.trim();
    const normalizedInput = normalizeSlashCommandInput(trimmedInput);
    if (normalizedInput.startsWith("/")) {
      const commandMatch = normalizedInput.match(/^\/(\w+)/);
      if (commandMatch) {
        const commandName = commandMatch[1].toLowerCase();
        // Only emit telemetry for supported commands
        const supportedCommand = getCommandsByScope("chat").find(cmd => 
          cmd.command.slice(1).toLowerCase() === commandName
        );
        if (supportedCommand) {
          eventBus.emit("slash-command-used", { 
            command: supportedCommand.telemetryKey || commandName,
            invocation_source: "input_dropdown"
          });
        }
      }
    }

    if (normalizedInput && !disabled) {
      onSend(normalizedInput);
      setInput("");
      setInputCaret(0);
      onValueChange?.("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showMetadataDropdown && metadataSuggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMetadataIndex((prev) =>
          prev === metadataSuggestions.length - 1 ? 0 : prev + 1,
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMetadataIndex((prev) =>
          prev === 0 ? metadataSuggestions.length - 1 : prev - 1,
        );
        return;
      }
      if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
        e.preventDefault();
        handleMetadataSelect(metadataSuggestions[metadataIndex]);
        return;
      }
    }

    if (showSlashPalette && filteredSlashCommands.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev === filteredSlashCommands.length - 1 ? 0 : prev + 1
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev === 0 ? filteredSlashCommands.length - 1 : prev - 1
        );
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        const cmd = filteredSlashCommands[selectedCommandIndex];
        applySlashCommand(cmd);
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const cmd = filteredSlashCommands[selectedCommandIndex];
        applySlashCommand(cmd);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="w-full flex flex-col gap-3">
      {(showSlashPalette || showMetadataDropdown) && (
        <div className="flex flex-col gap-2 max-h-[calc(100vh-18rem)] overflow-y-auto">
          {showSlashPalette && (
            <motion.div
              className="rounded-lg border border-glass bg-glass-elevated backdrop-blur-glass shadow-elevated p-2 max-h-[50vh] overflow-y-auto shadow-inset-border"
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-glass">
                <p className="text-xs uppercase tracking-wider text-text-subtle font-medium">
                  Commands
                </p>
                <p className="text-[11px] text-text-subtle font-medium">
                  ↑↓ · Enter · Press ? for help
                </p>
              </div>
              {filteredSlashCommands.length === 0 && (
                <div className="text-center text-xs text-text-muted py-4">
                  No commands match &quot;{slashQuery}&quot;
                </div>
              )}
              {filteredSlashCommands.map((command, index) => {
                const isSelected = index === selectedCommandIndex;
                return (
                  <motion.button
                    key={command.command}
                    onClick={() => applySlashCommand(command)}
                    onMouseEnter={() => setSelectedCommandIndex(index)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{
                      duration: duration.fast,
                      ease: easing.default,
                    }}
                    className={cn(
                      "w-full text-left px-2.5 py-2 rounded transition-colors flex items-center gap-3",
                      isSelected
                        ? "bg-glass-hover text-text-primary shadow-inset-border"
                        : "hover:bg-glass-hover text-text-muted"
                    )}
                  >
                    {command.emoji && (
                      <motion.span
                        className="text-lg flex-shrink-0 w-5 h-5 flex items-center justify-center"
                        animate={isSelected ? { scale: 1.1 } : { scale: 1 }}
                        transition={{ duration: duration.fast }}
                      >
                        {command.emoji}
                      </motion.span>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {command.label}
                      </p>
                      <p className="text-xs text-text-muted truncate">
                        {command.description}
                      </p>
                    </div>
                  </motion.button>
                );
              })}
            </motion.div>
          )}

          {showMetadataDropdown && (
            <motion.div
              className="rounded-lg border border-glass bg-glass-elevated backdrop-blur-glass shadow-elevated p-2 max-h-[50vh] overflow-y-auto shadow-inset-border"
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-glass">
                <p className="text-xs uppercase tracking-wider text-text-subtle font-medium">
                  Suggestions
                </p>
                <p className="text-[11px] text-text-subtle font-medium">
                  ↑↓ · Enter · Esc to dismiss
                </p>
              </div>
              {metadataSuggestions.map((suggestion, index) => {
                const descriptor = getSuggestionDescriptors(suggestion);
                const isSelected = index === metadataIndex;
                return (
                  <motion.button
                    key={`${suggestion.kind}-${descriptor.title}-${index}`}
                    onClick={() => handleMetadataSelect(suggestion)}
                    onMouseEnter={() => setMetadataIndex(index)}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ duration: duration.fast, ease: easing.default }}
                    className={cn(
                      "w-full text-left px-2.5 py-2 rounded transition-colors flex items-center gap-3",
                      isSelected
                        ? "bg-glass-hover text-text-primary shadow-inset-border"
                        : "hover:bg-glass-hover text-text-muted",
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{descriptor.title}</p>
                      {descriptor.subtitle && (
                        <p className="text-xs text-text-muted truncate">{descriptor.subtitle}</p>
                      )}
                    </div>
                    {descriptor.badge && (
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/70">
                        {descriptor.badge}
                      </span>
                    )}
                  </motion.button>
                );
              })}
              {metadataLoading && (
                <div className="text-center text-xs text-text-muted py-2">Fetching suggestions…</div>
              )}
              {metadataError && (
                <div className="text-center text-xs text-amber-300 py-2">
                  Suggestions unavailable: {metadataError}
                </div>
              )}
              {!metadataLoading && !metadataError && metadataSuggestions.length === 0 && (
                <div className="text-center text-xs text-text-muted py-2">
                  Keep typing to refine suggestions.
                </div>
              )}
            </motion.div>
          )}
        </div>
      )}

      <motion.div
        className="group relative rounded-3xl bg-glass-elevated backdrop-blur-glass px-3 py-2 flex items-end gap-3 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)] transition-all duration-200 ease-out"
        whileFocus={{ scale: 1.01 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
          {/* Keyboard shortcut hint tooltip */}
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none">
            <div className="bg-glass-elevated backdrop-blur-glass border border-glass rounded-lg px-2 py-1 text-xs text-text-muted shadow-elevated whitespace-nowrap">
              ⌘ Enter to send
            </div>
          </div>
          
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              const newValue = e.target.value;
              setInput(newValue);
               updateInputCaret(e.currentTarget);
              onValueChange?.(newValue);
            }}
            onKeyDown={handleKeyDown}
            placeholder="How can Cerebro help you?"
            disabled={disabled}
            autoFocus
            className="flex-1 bg-transparent text-text-primary placeholder-text-subtle resize-none outline-none text-[15px] leading-[1.5] max-h-[200px] focus-visible:outline-none caret-accent-primary caret-transition"
            rows={1}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 200) + "px";
            }}
            aria-label="Message input"
            data-testid="chat-input"
            onSelect={(e) => updateInputCaret(e.currentTarget)}
            onKeyUp={(e) => updateInputCaret(e.currentTarget)}
            onClick={(e) => updateInputCaret(e.currentTarget)}
          />

          <div className="flex items-center gap-2">
            {isProcessing && onStop && (
              <motion.button
                onClick={onStop}
                className="rounded-lg p-2.5 text-sm font-semibold transition-all duration-200 ease-out text-text-muted hover:text-text-primary hover:bg-gradient-to-r hover:from-accent-primary/20 hover:via-accent-primary/10 hover:to-transparent hover:shadow-[0_8px_20px_rgba(var(--accent-primary-rgb),0.25)] focus-visible:outline-none focus-visible:shadow-[0_0_0_2px_rgba(var(--accent-primary-rgb),0.45)]"
                title="Stop"
                whileHover={{ scale: 1.06 }}
                whileTap={{ scale: 0.95 }}
                transition={{ duration: 0.15, ease: "easeOut" }}
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 6h12v12H6z" />
                </svg>
              </motion.button>
            )}

            {onVoiceRecord && (
              <motion.button
                onClick={onVoiceRecord}
                disabled={disabled || isProcessing}
                className={cn(
                  "rounded-full p-3 transition-all duration-200 ease-out relative focus-visible:outline-none focus-visible:shadow-[0_0_0_2px_rgba(var(--accent-primary-rgb),0.45)] shadow-soft",
                  isRecording
                    ? "bg-accent-danger/15 text-accent-danger cursor-pointer shadow-glow-primary"
                    : disabled || isProcessing
                    ? "text-text-muted opacity-40 cursor-not-allowed bg-surface/50"
                    : "text-text-muted hover:text-text-primary hover:bg-gradient-to-r hover:from-accent-primary/20 hover:via-accent-primary/10 hover:to-transparent hover:shadow-[0_8px_20px_rgba(var(--accent-primary-rgb),0.25)] cursor-pointer"
                )}
                title={isRecording ? "Stop recording" : "Start voice recording"}
                aria-label={isRecording ? "Stop voice recording" : "Start voice recording"}
                aria-pressed={isRecording}
                whileHover={!disabled && !isProcessing ? { scale: 1.06 } : {}}
                whileTap={!disabled && !isProcessing ? { scale: 0.95 } : {}}
                animate={isRecording ? {
                  scale: [1, 1.08, 1],
                  transition: {
                    duration: 1.5,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }
                } : {}}
              >
                {/* Pulsing rings for recording state */}
                {isRecording && (
                  <>
                    <motion.span
                      className="absolute inset-0 rounded-full border-2 border-accent-danger"
                      animate={{
                        scale: [1, 1.3, 1],
                        opacity: [0.7, 0, 0.7],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeOut"
                      }}
                    />
                    <motion.span
                      className="absolute inset-0 rounded-full border-2 border-accent-danger"
                      animate={{
                        scale: [1, 1.5, 1],
                        opacity: [0.5, 0, 0.5],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeOut",
                        delay: 0.3
                      }}
                    />
                  </>
                )}

                <motion.svg
                  className="w-5 h-5 relative z-10"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  animate={isRecording ? { scale: [1, 1.1, 1] } : {}}
                  transition={{
                    duration: 0.5,
                    repeat: isRecording ? Infinity : 0,
                    ease: "easeInOut"
                  }}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                  {/* Recording indicator dot */}
                  {isRecording && (
                    <motion.circle
                      cx="12"
                      cy="12"
                      r="2"
                      fill="currentColor"
                      initial={{ scale: 0 }}
                      animate={{ scale: [0, 1, 0] }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: "easeInOut"
                      }}
                    />
                  )}
                </motion.svg>
              </motion.button>
            )}

            <motion.button
              onClick={handleSend}
              disabled={!input.trim() || disabled || isProcessing}
              className={cn(
                "rounded-lg p-2.5 transition-all duration-200 ease-out focus-visible:outline-none focus-visible:shadow-[0_0_0_2px_rgba(var(--accent-primary-rgb),0.45)]",
                !input.trim() || disabled || isProcessing
                  ? "text-text-muted opacity-40 cursor-not-allowed bg-surface/50"
                  : "text-accent-primary hover:bg-gradient-to-r hover:from-accent-primary/20 hover:via-accent-primary/10 hover:to-transparent hover:shadow-[0_8px_20px_rgba(var(--accent-primary-rgb),0.25)] cursor-pointer shadow-soft"
              )}
              title="Send"
              whileHover={!input.trim() || disabled || isProcessing ? {} : { scale: 1.06 }}
              whileTap={!input.trim() || disabled || isProcessing ? {} : { scale: 0.95 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              animate={isProcessing ? {
                boxShadow: [
                  "0 0 15px rgba(139, 92, 246, 0.4), 0 0 30px rgba(139, 92, 246, 0.2)",
                  "0 0 25px rgba(139, 92, 246, 0.6), 0 0 50px rgba(139, 92, 246, 0.3)",
                  "0 0 15px rgba(139, 92, 246, 0.4), 0 0 30px rgba(139, 92, 246, 0.2)"
                ]
              } : {}}
              style={isProcessing ? {
                boxShadow: "0 0 15px rgba(139, 92, 246, 0.4), 0 0 30px rgba(139, 92, 246, 0.2)"
              } : {}}
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M5 12h14M12 5l7 7-7 7"
                />
              </svg>
            </motion.button>
          </div>
        </motion.div>
    </div>
  );
}
