"use client";

import { useState, useEffect } from "react";
import CommandPalette from "@/components/CommandPalette";
import DocumentPreviewModal from "@/components/DocumentPreviewModal";

function ClientLayout({ children }: { children: React.ReactNode }) {
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [documentPreview, setDocumentPreview] = useState<{
    isOpen: boolean;
    filePath: string;
    fileType: string;
  }>({ isOpen: false, filePath: "", fileType: "" });

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

  return (
    <>
      {children}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onOpenDocument={handleOpenDocument}
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
