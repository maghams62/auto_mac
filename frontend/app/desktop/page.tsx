"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import SpotifyMiniPlayer from "@/components/SpotifyMiniPlayer";
import { isElectron, collapseToSpotlight } from "@/lib/electron";
import logger from "@/lib/logger";
import { BootProvider, useBootContext } from "@/components/BootProvider";
import DesktopExpandAnimation from "@/components/DesktopExpandAnimation";
import { useIsElectronRuntime } from "@/hooks/useIsElectron";

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
  const [isReady, setIsReady] = useState(false);
  const [showExpandOverlay, setShowExpandOverlay] = useState(true);
  const { bootPhase } = useBootContext();
  const isElectronRuntime = useIsElectronRuntime();

  useEffect(() => {
    logger.info("[DESKTOP] Page mounted", { isElectron: isElectron() });
    
    if (bootPhase === "ready") {
      setIsReady(true);
    }
  }, [bootPhase]);

  useEffect(() => {
    if (!isReady) return;
    const timeout = setTimeout(() => setShowExpandOverlay(false), 350);
    return () => clearTimeout(timeout);
  }, [isReady]);

  useEffect(() => {
    logger.info("[DESKTOP] Expand overlay state changed", {
      visible: showExpandOverlay || !isReady,
      bootReady: isReady,
    });
  }, [showExpandOverlay, isReady]);

  const handleCollapse = () => {
    logger.info("[DESKTOP] Collapse to spotlight requested");
    collapseToSpotlight();
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-neutral-950 via-neutral-900 to-neutral-950 flex flex-col">
      <DesktopExpandAnimation
        isVisible={showExpandOverlay || !isReady}
        headline={isReady ? "Workspace ready" : "Expanding workspace"}
        subhead={isReady ? "Bringing your context forward" : "Loading chat context…"}
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
            <motion.button
              onClick={handleCollapse}
              className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-muted hover:text-text-primary bg-glass/20 hover:bg-glass/40 rounded-lg transition-all"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              title="Collapse to Spotlight (⌘+Option+K)"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
              <span>Spotlight Mode</span>
            </motion.button>
          )}
        </div>
      </header>

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Interface takes most of the space */}
        <div className="flex-1 flex flex-col">
          {bootPhase === "error" ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-4">
                <div className="text-red-400 font-mono text-sm">Connection failed</div>
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-glass/20 hover:bg-glass/40 rounded-lg text-sm transition-all"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: isReady ? 1 : 0, y: isReady ? 0 : 20 }}
              transition={{ duration: 0.3 }}
              className="flex-1"
            >
              <DesktopChat />
            </motion.div>
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

