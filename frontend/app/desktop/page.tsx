"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import SpotifyMiniPlayer from "@/components/SpotifyMiniPlayer";
import { isElectron, collapseToSpotlight } from "@/lib/electron";
import logger from "@/lib/logger";
import { BootProvider, useBootContext } from "@/components/BootProvider";
import DesktopExpandAnimation from "@/components/DesktopExpandAnimation";
import { useIsElectronRuntime } from "@/hooks/useIsElectron";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

const DesktopChat = dynamic(() => import("@/components/ChatInterface"), {
  ssr: false,
  loading: () => <DesktopLoadingState />,
});

export default function DesktopPage() {
  return (
    <BootProvider>
      <DesktopContent />
    </BootProvider>
  );
}

function DesktopContent() {
  const [hasHydrated, setHasHydrated] = useState(false);
  const { bootPhase, bootError } = useBootContext();
  const isElectronRuntime = useIsElectronRuntime();
  const searchParams = useSearchParams();
  const initialStateParam = searchParams?.get("state");
  const pendingFromHost = initialStateParam === "pending";
  const frontendAttempts = searchParams?.get("attempts");
  const [hostReady, setHostReady] = useState(!pendingFromHost);
  const isHostPending = pendingFromHost && !hostReady;

  useEffect(() => {
    setHasHydrated(true);
  }, []);

  useEffect(() => {
    logger.info("[DESKTOP] Page mounted", { isElectron: isElectron() });
  }, []);
    
  const isBootReady = bootPhase === "ready";

  useEffect(() => {
    if (isBootReady && !hostReady) {
      setHostReady(true);
      logger.info("[DESKTOP] Host marked ready after boot");
    }
  }, [isBootReady, hostReady]);

  useEffect(() => {
    logger.info("[DESKTOP] Boot phase change", {
      bootPhase,
      bootError,
      pendingFromHost,
      frontendAttempts,
    });
  }, [bootPhase, bootError, pendingFromHost, frontendAttempts]);

  const overlayVisible = (bootPhase !== "error") && (isHostPending || bootPhase === "assets");

  useEffect(() => {
    logger.info("[DESKTOP] Expand overlay state changed", {
      visible: overlayVisible,
      bootPhase,
      hostPending: isHostPending,
    });
  }, [overlayVisible, bootPhase, isHostPending]);

  const handleCollapse = () => {
    logger.info("[DESKTOP] Collapse to spotlight requested");
    collapseToSpotlight();
  };

  const overlayCopy = useMemo(() => {
    if (bootPhase === "error") {
      return {
        headline: "Desktop unavailable",
        subhead: bootError || "Could not connect to Cerebros services.",
        steps: ["Retry from Spotlight", "Confirm api_server.py is running"],
      };
    }
    if (bootPhase === "ready") {
      return {
        headline: "Workspace ready",
        subhead: "Bringing your context forward",
        steps: [],
      };
    }
    if (bootPhase === "websocket") {
      return {
        headline: "Connecting to Cerebros",
        subhead: "Waiting for the chat WebSocket…",
        steps: ["Connecting to backend", "Syncing history", "Warming slash commands"],
      };
    }
    if (isHostPending) {
      return {
        headline: "Waiting for desktop bundle",
        subhead: "Next.js dev server is still starting…",
        steps: ["Detecting local dev server", "Requesting /desktop route", "Streaming UI assets"],
      };
    }
    if (bootPhase === "assets") {
      return {
        headline: "Expanding workspace",
        subhead: "Loading chat context…",
        steps: ["Booting command router", "Priming slash commands", "Syncing Spotify + Slack state"],
      };
    }
    return {
      headline: "Expanding workspace",
      subhead: "Bringing chat online…",
      steps: ["Connecting to backend", "Syncing history", "Warming slash commands"],
    };
  }, [bootPhase, bootError, isHostPending]);

  if (!hasHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-neutral-950 via-neutral-900 to-neutral-950">
        <DesktopLoadingState />
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-neutral-950 via-neutral-900 to-neutral-950 flex flex-col">
      <DesktopExpandAnimation
        isVisible={overlayVisible}
        headline={overlayCopy.headline}
        subhead={overlayCopy.subhead}
        statusSteps={overlayCopy.steps}
      />
      {/* Header with collapse button */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-glass/20 bg-glass/10 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-primary to-purple-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">C</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-text-primary">Cerebros</h1>
            <p className="text-xs text-text-muted">Desktop View</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Collapse to Spotlight button */}
          {isElectronRuntime && (
            <button
              onClick={handleCollapse}
              className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-muted hover:text-text-primary bg-glass/20 hover:bg-glass/40 rounded-lg"
              title="Collapse to Spotlight (⌘+Option+K)"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
              <span>Spotlight Mode</span>
            </button>
          )}
        </div>
      </header>

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Keep chat mounted even during error states so reconnection logic can recover */}
        <div className="relative flex-1 flex flex-col">
          <div
            className={cn(
              "flex-1 transition-opacity duration-200",
              bootPhase === "error" ? "pointer-events-none opacity-30" : "opacity-100",
            )}
          >
            <DesktopChat />
          </div>
          {bootPhase === "error" && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-neutral-950/80 backdrop-blur">
              <div className="text-center space-y-4 max-w-sm">
                <div className="text-red-400 font-mono text-sm">Connection failed</div>
                {bootError && (
                  <p className="text-text-muted text-sm">
                    {bootError}
                  </p>
                )}
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-glass/20 hover:bg-glass/40 rounded-lg text-sm"
                >
                  Retry
                </button>
                <button
                  onClick={handleCollapse}
                  className="px-4 py-2 bg-transparent border border-white/15 hover:border-white/40 rounded-lg text-sm text-text-muted hover:text-text-primary"
                >
                  Back to Spotlight
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer with Spotify */}
      <footer className="border-t border-glass/20">
        <SpotifyMiniPlayer variant="launcher-full" />
      </footer>
    </div>
  );
}

function DesktopLoadingState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 bg-gradient-to-br from-neutral-950/40 via-neutral-900/60 to-neutral-950/40 text-text-muted">
      <div className="text-xs uppercase tracking-[0.3em] text-text-muted/60">Preparing</div>
      <div className="text-sm text-text-muted">Loading chat workspace…</div>
    </div>
  );
}

