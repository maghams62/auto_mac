"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { overlayFade, modalSlideDown } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/apiConfig";

interface DocumentPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  filePath: string;
  fileType?: "pdf" | "html" | "image";
}

export default function DocumentPreviewModal({
  isOpen,
  onClose,
  filePath,
  fileType = "pdf",
}: DocumentPreviewModalProps) {
  const apiBaseUrl = getApiBaseUrl();
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
      // Reset error state when modal opens
      setPreviewError(null);
      setIsLoading(true);
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen, filePath]);

  // Handle preview load errors
  const handlePreviewError = (error: string) => {
    setPreviewError(error);
    setIsLoading(false);
  };

  // Check if file is accessible before loading
  useEffect(() => {
    if (!isOpen || !filePath) return;

    // Try to fetch the preview URL to check if it's accessible
    const checkPreviewAccess = async () => {
      const previewUrl = `${apiBaseUrl}/api/files/preview?path=${encodeURIComponent(filePath)}`;
      try {
        const response = await fetch(previewUrl, { method: "HEAD" });
        if (!response.ok) {
          if (response.status === 403) {
            handlePreviewError("Preview not available: File is outside allowed directories");
          } else if (response.status === 404) {
            handlePreviewError("Preview not available: File not found");
          } else {
            handlePreviewError(`Preview not available: Server error (${response.status})`);
          }
        } else {
          setIsLoading(false);
        }
      } catch (err) {
        handlePreviewError("Preview not available: Unable to load file");
      }
    };

    checkPreviewAccess();
  }, [isOpen, filePath, apiBaseUrl]);

  if (!isOpen) return null;

  const previewUrl = `${apiBaseUrl}/api/files/preview?path=${encodeURIComponent(filePath)}`;
  const fileName = filePath.split("/").pop() || filePath;

  return (
    <AnimatePresence>
      <motion.div
        initial="hidden"
        animate="visible"
        exit="hidden"
        variants={overlayFade}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Backdrop with blur */}
        <div className="absolute inset-0 bg-black/70 backdrop-blur-md" />

        {/* Modal Window */}
        <motion.div
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={modalSlideDown}
          className={cn(
            "relative w-full max-w-6xl max-h-[90vh] overflow-hidden",
            "bg-gradient-to-br from-neutral-900/95 via-neutral-800/95 to-neutral-900/95",
            "backdrop-blur-xl rounded-2xl",
            "border border-white/10 shadow-2xl",
            "flex flex-col"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/5">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-accent-primary/60 animate-pulse" />
              <h2 className="text-lg font-semibold text-text-primary truncate" title={fileName}>
                {fileName}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-primary transition-colors p-1 rounded-lg hover:bg-white/5"
              aria-label="Close"
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
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Content Area */}
          <div className="flex-1 overflow-hidden">
            {previewError ? (
              <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                <div className="w-16 h-16 rounded-full bg-danger-bg/20 flex items-center justify-center mb-4">
                  <svg
                    className="w-8 h-8 text-accent-danger"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-text-primary mb-2">
                  Preview Not Available
                </h3>
                <p className="text-text-muted mb-4 max-w-md">
                  {previewError}
                </p>
                <div className="text-sm text-text-subtle">
                  <p>You can still:</p>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>Open the file in Finder using the "Reveal" button</li>
                    <li>Copy the file path to access it manually</li>
                  </ul>
                </div>
              </div>
            ) : (
              <>
                {fileType === "pdf" && (
                  <iframe
                    src={previewUrl}
                    className="w-full h-full min-h-[600px] border-0"
                    title={fileName}
                    onError={() => handlePreviewError("Failed to load PDF preview")}
                    onLoad={() => setIsLoading(false)}
                  />
                )}
                {fileType === "html" && (
                  <iframe
                    src={previewUrl}
                    className="w-full h-full min-h-[600px] border-0"
                    title={fileName}
                    onError={() => handlePreviewError("Failed to load HTML preview")}
                    onLoad={() => setIsLoading(false)}
                  />
                )}
                {fileType === "image" && (
                  <div className="flex items-center justify-center p-8 h-full">
                    {isLoading && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-8 h-8 border-2 border-accent-primary border-t-transparent rounded-full animate-spin" />
                      </div>
                    )}
                    <img
                      src={previewUrl}
                      alt={fileName}
                      className="max-w-full max-h-full object-contain"
                      onError={() => handlePreviewError("Failed to load image preview")}
                      onLoad={() => setIsLoading(false)}
                    />
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-white/10 bg-white/5 flex items-center justify-between">
            <div className="text-xs text-text-muted">
              Press <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-text-muted">ESC</kbd> to close
            </div>
            <div className="flex items-center gap-2">
              <a
                href={previewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-accent-primary/20 hover:bg-accent-primary/30 text-accent-primary rounded-lg transition-colors text-sm font-medium"
              >
                Open in New Tab
              </a>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-glass hover:bg-glass-hover text-text-primary rounded-lg transition-colors text-sm font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

