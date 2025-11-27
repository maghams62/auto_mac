"use client";

import { useState, useEffect } from "react";
import CommandPalette from "@/components/CommandPalette";
import DocumentPreviewModal from "@/components/DocumentPreviewModal";
import PreferencesModal from "@/components/PreferencesModal";
import SpotifyMiniPlayer from "@/components/SpotifyMiniPlayer";
import { useGlobalEventBus } from "@/lib/telemetry";
import { isElectron, hideWindow } from "@/lib/electron";

function ClientLayout({ children }: { children: React.ReactNode }) {
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [pendingPaletteQuery, setPendingPaletteQuery] = useState<string | null>(null);
  const [pendingPaletteSource, setPendingPaletteSource] = useState<"files" | "folder" | undefined>(undefined);
  const [isPreferencesOpen, setIsPreferencesOpen] = useState(false);
  const [documentPreview, setDocumentPreview] = useState<{
    isOpen: boolean;
    filePath: string;
    fileType: string;
  }>({ isOpen: false, filePath: "", fileType: "" });
  const eventBus = useGlobalEventBus();

  // Global keyboard handler for Command+K and Escape (Electron)
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // Command+K to open palette
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(true);
      }

      // Escape to hide window (Electron only)
      if (e.key === 'Escape' && isElectron()) {
        // Only hide if no modals are open
        if (!isCommandPaletteOpen && !documentPreview.isOpen && !isPreferencesOpen) {
          hideWindow();
        }
      }

      // Command+, to open preferences (Electron only)
      if ((e.metaKey || e.ctrlKey) && e.key === ',' && isElectron()) {
        e.preventDefault();
        setIsPreferencesOpen(true);
      }
    };

    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => document.removeEventListener('keydown', handleGlobalKeyDown);
  }, [isCommandPaletteOpen, documentPreview.isOpen, isPreferencesOpen]);

  const handleOpenDocument = (filePath: string, highlightOffsets?: [number, number][]) => {
    // Determine file type from extension
    const fileExtension = filePath.split('.').pop()?.toLowerCase() || '';
    let fileType: "pdf" | "html" | "image" = "pdf";

    if (['pdf'].includes(fileExtension)) {
      fileType = "pdf";
    } else if (['html', 'htm'].includes(fileExtension)) {
      fileType = "html";
    } else if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(fileExtension)) {
      fileType = "image";
    }

    setDocumentPreview({
      isOpen: true,
      filePath,
      fileType
    });
  };

  const handleCloseDocumentPreview = () => {
    setDocumentPreview({ isOpen: false, filePath: "", fileType: "" });
  };

  useEffect(() => {
    if (!eventBus) return;

    const unsubscribePalette = eventBus.subscribe("open-command-palette", (payload?: { query?: string; source?: "files" | "folder" }) => {
      setPendingPaletteQuery(payload?.query ?? null);
      setPendingPaletteSource(payload?.source);
      setIsCommandPaletteOpen(true);
    });

    const unsubscribePreferences = eventBus.subscribe("open-preferences", () => {
      setIsPreferencesOpen(true);
    });

    return () => {
      unsubscribePalette();
      unsubscribePreferences();
    };
  }, [eventBus]);

  // Listen for Electron preferences event
  useEffect(() => {
    if (isElectron() && window.electronAPI?.onOpenPreferences) {
      window.electronAPI.onOpenPreferences(() => {
        setIsPreferencesOpen(true);
      });
    }
  }, []);

  return (
    <>
      {children}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => {
          setIsCommandPaletteOpen(false);
          setPendingPaletteSource(undefined);

          // Hide Electron window if running in Electron
          if (isElectron()) {
            hideWindow();
          }
        }}
        initialQuery={pendingPaletteQuery ?? ""}
        source={pendingPaletteSource}
        onOpenDocument={handleOpenDocument}
        onMount={() => {
          setPendingPaletteQuery(null);
          setPendingPaletteSource(undefined);
        }}
      />
      <DocumentPreviewModal
        isOpen={documentPreview.isOpen}
        onClose={handleCloseDocumentPreview}
        filePath={documentPreview.filePath}
        fileType={documentPreview.fileType as any}
      />
      <PreferencesModal
        isOpen={isPreferencesOpen}
        onClose={() => setIsPreferencesOpen(false)}
      />
      {/* Spotify mini-player is now embedded in CommandPalette for launcher mode */}
    </>
  );
}

export default ClientLayout;
