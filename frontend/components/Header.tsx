"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useThemeTokens } from "@/lib/theme/tokens";

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
}

export default function Header({
  isConnected = true,
  messageCount = 0,
  onClearSession,
  onShowHelp
}: HeaderProps) {
  const tokens = useThemeTokens();

  return (
    <header className={cn(
      "sticky top-0 z-50 border-b backdrop-blur-glass",
      "bg-glass-elevated/60 border-glass/50"
    )}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
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
              <h1 className="text-lg font-semibold text-text-primary tracking-tight">
                Cerebro
              </h1>
              <p className="text-xs text-text-muted font-medium">
                Mac OS Assistant
              </p>
            </div>
          </div>

          {/* Center Section - Status Pills */}
          <div className="flex items-center gap-2">
            {/* Connection Status */}
            <div className={cn(
              "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium",
              "bg-glass backdrop-blur-glass border border-glass/50",
              isConnected
                ? "text-accent-success border-accent-success/20"
                : "text-accent-danger border-accent-danger/20"
            )}>
              <div className={cn(
                "w-2 h-2 rounded-full",
                isConnected ? "bg-accent-success animate-pulse" : "bg-accent-danger"
              )} />
              <span>{isConnected ? "Connected" : "Disconnected"}</span>
            </div>

            {/* Message Count */}
            {messageCount > 0 && (
              <div className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium",
                "bg-glass backdrop-blur-glass border border-glass/50",
                "text-text-muted"
              )}>
                <span>{messageCount} messages</span>
              </div>
            )}

            {/* Time */}
            <div className={cn(
              "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium",
              "bg-glass backdrop-blur-glass border border-glass/50",
              "text-text-muted"
            )}>
              <ClientTime />
            </div>
          </div>

          {/* Right Section - Quick Actions */}
          <div className="flex items-center gap-1">
            {onShowHelp && (
              <button
                onClick={onShowHelp}
                className={cn(
                  "inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium",
                  "text-text-muted hover:text-text-primary hover:bg-glass-hover",
                  "transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                )}
                title="Help & Commands"
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
                  "inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium",
                  "text-text-muted hover:text-accent-danger hover:bg-accent-danger/10",
                  "transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-accent-danger/50"
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
