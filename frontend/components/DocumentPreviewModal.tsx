"use client";

import { useEffect } from "react";
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
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

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
            {fileType === "pdf" && (
              <iframe
                src={previewUrl}
                className="w-full h-full min-h-[600px] border-0"
                title={fileName}
              />
            )}
            {fileType === "html" && (
              <iframe
                src={previewUrl}
                className="w-full h-full min-h-[600px] border-0"
                title={fileName}
              />
            )}
            {fileType === "image" && (
              <div className="flex items-center justify-center p-8 h-full">
                <img
                  src={previewUrl}
                  alt={fileName}
                  className="max-w-full max-h-full object-contain"
                />
              </div>
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

