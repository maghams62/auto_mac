"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import CommandPalette from "@/components/CommandPalette";
import { isElectron, hideWindow, onWindowShown, onWindowHidden, unlockWindow, getWindowState } from "@/lib/electron";
import logger from "@/lib/logger";
import { useIsElectronRuntime } from "@/hooks/useIsElectron";

export default function LauncherPage() {
  const isElectronRuntime = useIsElectronRuntime();
  // In launcher mode, always show the palette - hiding just hides the Electron window
  const [isOpen, setIsOpen] = useState(true);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const startTime = performance.now();
    logger.info("[LAUNCHER] Page mounted", { 
      isElectron: isElectron(),
      timestamp: new Date().toISOString()
    });
    
    // Log when fully rendered
    requestAnimationFrame(() => {
      const renderTime = performance.now() - startTime;
      logger.info("[LAUNCHER] First paint complete", { renderTimeMs: renderTime.toFixed(2) });
    });
    
    // Listen for window shown events from Electron to refocus input
    if (isElectron()) {
      onWindowShown(() => {
        logger.info("[LAUNCHER] Window shown event received - resetting state");

        // FAIL-SAFE: Always unlock when window is shown to prevent stuck lock state
        // The lock will be re-applied when user submits a query if needed
        unlockWindow();

        setIsOpen(true);
        setQuery(""); // Clear previous query
        // Focus the input after a short delay to ensure DOM is ready
        setTimeout(() => {
          inputRef.current?.focus();
          logger.debug("[LAUNCHER] Input focused after show");
        }, 50);

        // DIAGNOSTIC: Verify window state after render completes
        setTimeout(async () => {
          const state = await getWindowState();
          if (state) {
            logger.info("[DIAGNOSTIC] Window state after show:", {
              visible: state.visible,
              focused: state.focused,
              locked: state.locked,
              bounds: state.bounds
            });

            // Alert if window is not in expected state
            if (!state.visible) {
              logger.error("[BUG] Window state shows not visible after show event!");
            }
          }
        }, 150);
      });

      // Listen for window hidden events (user clicked away - Spotlight behavior)
      onWindowHidden(() => {
        logger.info("[LAUNCHER] Window hidden event received - user clicked away");
        // Ensure window is unlocked when hidden
        unlockWindow();
        // Reset state for next invocation
        setQuery("");
      });
    }
  }, []);

  const handleClose = useCallback(() => {
    logger.info("[LAUNCHER] Closing launcher", { isElectron: isElectron() });
    // In Electron, hide the window instead of closing the palette
    if (isElectron()) {
      hideWindow();
    } else {
      // In browser mode (development), just hide the palette
      setIsOpen(false);
    }
  }, []);

  // Handle Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [handleClose]);

  // Re-show the palette when window becomes visible (browser fallback)
  useEffect(() => {
    if (typeof window !== "undefined" && !isElectron()) {
      const handleVisibilityChange = () => {
        if (document.visibilityState === "visible") {
          setIsOpen(true);
        }
      };
      document.addEventListener("visibilitychange", handleVisibilityChange);
      return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
    }
  }, []);

  // For browser mode development, allow reopening with Cmd+K
  useEffect(() => {
    if (!isElectron()) {
      const handleKeyDown = (e: KeyboardEvent) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "k") {
          e.preventDefault();
          setIsOpen(true);
        }
      };
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, []);

  // Handler to pass focus ref to CommandPalette
  const handleMount = useCallback((ref: HTMLInputElement | null) => {
    if (ref) {
      (inputRef as React.MutableRefObject<HTMLInputElement | null>).current = ref;
    }
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-neutral-900 via-neutral-800 to-neutral-900">
      <CommandPalette
        isOpen={isOpen}
        onClose={handleClose}
        mode="launcher"
        initialQuery={query}
        onMount={handleMount}
      />
      
      {/* Show hint when palette is closed (browser mode only) */}
      {!isOpen && !isElectronRuntime && (
        <div className="fixed inset-0 flex items-center justify-center">
          <div className="text-center text-white/60">
            <p className="text-lg mb-2">Launcher hidden</p>
            <p className="text-sm">Press <kbd className="px-2 py-1 bg-white/10 rounded">⌘K</kbd> to reopen</p>
          </div>
        </div>
      )}
    </div>
  );
}

