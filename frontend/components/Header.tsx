"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

// Prevent hydration mismatch by rendering time only on client
function ClientTime() {
  const [currentTime, setCurrentTime] = useState<Date | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setCurrentTime(new Date());

    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  if (!mounted || !currentTime) {
    return <span>--:--</span>;
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return <span>{formatTime(currentTime)}</span>;
}

interface HeaderProps {
  isConnected?: boolean;
  messageCount?: number;
  onClearSession?: () => void;
  onShowHelp?: () => void;
  planActive?: boolean;
  onTogglePlanTrace?: () => void;
  isTraceOpen?: boolean;
}

export default function Header({
  isConnected = true,
  messageCount = 0,
  onClearSession,
  onShowHelp,
  planActive = false,
  onTogglePlanTrace,
  isTraceOpen = false
}: HeaderProps) {
  return (
    <header className={cn(
      "sticky top-0 z-50 border-b backdrop-blur-glass shadow-elevated",
      "bg-glass-elevated/95 border-glass/50"
    )}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Left Section - Brand */}
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-8 h-8 rounded-xl flex items-center justify-center transition-all",
              "bg-gradient-to-br from-accent-primary to-accent-primary-hover shadow-glow-primary"
            )}>
              <span className="text-white font-bold text-sm">C</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-text-primary tracking-tight flex items-center gap-2">
                Cerebro
                <span className="text-xs px-1.5 py-0.5 rounded bg-glass text-text-muted font-medium">
                  beta
                </span>
              </h1>
              <p className="text-sm text-text-muted font-semibold">
                Mac OS Assistant
              </p>
            </div>
          </div>

          {/* Center Section - Status Bar */}
          <div className="flex items-center gap-4">
            {/* Status Indicator */}
            <div className={cn(
              "inline-flex items-center gap-3 px-4 py-2 rounded-lg text-sm font-medium",
              "bg-glass-elevated/90 backdrop-blur-glass border border-glass/70",
              "text-text-primary"
            )}>
              <div className={cn(
                "w-2 h-2 rounded-full",
                isConnected ? "bg-accent-success animate-pulse" : "bg-accent-danger"
              )} />
              <span className="font-semibold">
                {isConnected ? "Connected" : "Disconnected"}
                {messageCount > 0 && (
                  <span className="text-text-muted font-normal ml-2">
                    • {messageCount} messages
                  </span>
                )}
                {planActive && (
                  <span className="ml-2 inline-flex items-center gap-1 text-accent-primary font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-primary animate-pulse" />
                    Plan running
                  </span>
                )}
              </span>
            </div>

            {/* Time */}
            <div className={cn(
              "text-sm font-semibold text-text-muted"
            )}>
              <ClientTime />
            </div>
          </div>

          {/* Right Section - Quick Actions */}
          <div className="flex items-center gap-2">
            {planActive && onTogglePlanTrace && (
              <button
                onClick={onTogglePlanTrace}
                className={cn(
                  "inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-all duration-200 ease-out focus:outline-none focus:ring-2",
                  isTraceOpen
                    ? "text-accent-primary bg-surface-elevated/80 border border-accent-primary/40 shadow-soft focus:ring-accent-primary/40"
                    : "text-text-muted hover:text-text-primary hover:bg-surface-elevated/80 focus:ring-accent-primary/30"
                )}
                title={isTraceOpen ? "Hide plan trace" : "Show plan trace"}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M6 12a3 3 0 116 0 3 3 0 01-6 0z" strokeWidth="1.5" />
                  <path d="M12 5l4-2 4 2v4l-4 2-4-2V5z" strokeWidth="1.5" />
                  <path d="M12 13v6l4 2 4-2v-6" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            )}

            {onShowHelp && (
              <button
                onClick={onShowHelp}
                className={cn(
                  "inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium",
                  "text-text-muted hover:text-text-primary hover:bg-surface-elevated/80 hover:shadow-soft",
                  "transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                )}
                title="Help & Commands (⌘?)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
            )}

            {onClearSession && messageCount > 0 && (
              <button
                onClick={onClearSession}
                className={cn(
                  "inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium",
                  "text-text-muted hover:text-accent-danger hover:bg-surface-elevated/80 hover:shadow-soft",
                  "transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-accent-danger/50"
                )}
                title="Clear Session"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
