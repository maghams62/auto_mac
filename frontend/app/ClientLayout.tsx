"use client";

import { useState, useEffect } from "react";
import CommandPalette from "@/components/CommandPalette";
import DocumentPreviewModal from "@/components/DocumentPreviewModal";
import { useGlobalEventBus } from "@/lib/telemetry";

function ClientLayout({ children }: { children: React.ReactNode }) {
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [pendingPaletteQuery, setPendingPaletteQuery] = useState<string | null>(null);
  const [pendingPaletteSource, setPendingPaletteSource] = useState<"files" | "folder" | undefined>(undefined);
  const [documentPreview, setDocumentPreview] = useState<{
    isOpen: boolean;
    filePath: string;
    fileType: string;
  }>({ isOpen: false, filePath: "", fileType: "" });
  const eventBus = useGlobalEventBus();

  // Global keyboard handler for Command+K
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(true);
      }
    };

    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => document.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

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

    const unsubscribe = eventBus.subscribe("open-command-palette", (payload?: { query?: string; source?: "files" | "folder" }) => {
      setPendingPaletteQuery(payload?.query ?? null);
      setPendingPaletteSource(payload?.source);
      setIsCommandPaletteOpen(true);
    });

    return () => {
      unsubscribe();
    };
  }, [eventBus]);

  return (
    <>
      {children}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => {
          setIsCommandPaletteOpen(false);
          setPendingPaletteSource(undefined);
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
    </>
  );
}

export default ClientLayout;
