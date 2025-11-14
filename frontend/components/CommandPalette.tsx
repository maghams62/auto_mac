"use client";

import { useState, useEffect, useCallback, useMemo, useRef, KeyboardEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { getApiBaseUrl } from "@/lib/apiConfig";
import { overlayFade, modalSlideDown } from "@/lib/motion";
import { duration, easing } from "@/lib/motion";
import logger from "@/lib/logger";

interface SearchResult {
  result_type: "document" | "image";
  file_path: string;
  file_name: string;
  file_type: string;
  page_number?: number;
  total_pages?: number;
  similarity_score: number;
  snippet: string;
  highlight_offsets: [number, number][];
  breadcrumb: string;
  thumbnail_url?: string;
  preview_url?: string;
  metadata?: {
    width?: number;
    height?: number;
  };
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onMount?: () => void;
  onOpenDocument?: (filePath: string, highlightOffsets?: [number, number][]) => void;
  onOpenExternal?: (filePath: string) => void;
  initialQuery?: string;
  source?: "files" | "folder";
}

export default function CommandPalette({
  isOpen,
  onClose,
  onMount,
  onOpenDocument,
  onOpenExternal,
  initialQuery = "",
  source = "files"
}: CommandPaletteProps) {
  const baseUrl = getApiBaseUrl();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [previewMode, setPreviewMode] = useState<'closed' | 'loading' | 'previewing'>('closed');
  const [previewData, setPreviewData] = useState<SearchResult | null>(null);

  // Define handler functions before useEffect to avoid initialization errors
  const handleSelectResult = useCallback((result: SearchResult) => {
    if (onOpenDocument) {
      onOpenDocument(result.file_path, result.highlight_offsets);
    }
    onClose();
  }, [onOpenDocument, onClose]);

  const handleOpenExternal = useCallback(async (result: SearchResult) => {
    if (onOpenExternal) {
      onOpenExternal(result.file_path);
    } else {
      // Fallback: Use the reveal-file API
      try {
        const response = await fetch(`${baseUrl}/api/reveal-file`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ path: result.file_path }),
        });

        if (!response.ok) {
          throw new Error('Failed to open externally');
        }
      } catch (error) {
        console.error('Error opening file externally:', error);
      }
    }
    onClose();
  }, [onOpenExternal, baseUrl, onClose]);

  const togglePreview = useCallback((result: SearchResult) => {
    if (previewMode === 'closed' || previewData?.file_path !== result.file_path) {
      setPreviewMode('loading');
      setPreviewData(result);
      // Simulate loading delay for now
      setTimeout(() => setPreviewMode('previewing'), 300);
    } else {
      setPreviewMode('closed');
      setPreviewData(null);
    }
  }, [previewMode, previewData]);

  // Debounced search - use ref instead of state to avoid infinite loop
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(
        `${baseUrl}/api/universal-search?q=${encodeURIComponent(searchQuery)}&limit=10`
      );

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status}`);
      }

      const data = await response.json();
      setResults(data.results || []);
      setSelectedIndex(0);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl]);

  // Debounced search effect
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    const timer = setTimeout(() => {
      performSearch(query);
    }, 200);

    debounceTimerRef.current = timer;

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [query, performSearch]); // Remove debounceTimer from deps

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setQuery(initialQuery);
      setResults([]);
      setSelectedIndex(0);
      setPreviewMode('closed');
      setPreviewData(null);
      setIsLoading(false);
      logger.info("[COMMAND PALETTE] Opened", { source, initialQuery });
      onMount?.();
    }
  }, [isOpen, initialQuery, onMount, source]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        if (previewMode !== 'closed') {
          setPreviewMode('closed');
          setPreviewData(null);
        } else {
          onClose();
        }
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex(prev =>
          prev === results.length - 1 ? 0 : prev + 1
        );
        return;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(prev =>
          prev === 0 ? results.length - 1 : prev - 1
        );
        return;
      }

      if (e.key === "Enter") {
        e.preventDefault();
        if (results[selectedIndex]) {
          if (e.metaKey || e.ctrlKey) {
            // Cmd/Ctrl+Enter: Open externally
            handleOpenExternal(results[selectedIndex]);
          } else {
            // Enter: Open in app
            handleSelectResult(results[selectedIndex]);
          }
        }
        return;
      }

      if (e.key === " ") {
        e.preventDefault();
        if (results[selectedIndex]) {
          togglePreview(results[selectedIndex]);
        }
        return;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, results, selectedIndex, previewMode, onClose, handleOpenExternal, handleSelectResult, togglePreview]);

  const getFileIcon = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case 'pdf':
        return '📄';
      case 'docx':
      case 'doc':
        return '📝';
      case 'txt':
        return '📃';
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
      case 'webp':
        return '🖼️';
      default:
        return '📄';
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial="hidden"
        animate="visible"
        exit="hidden"
        variants={overlayFade}
        className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4"
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            onClose();
          }
        }}
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

        {/* Modal Container */}
        <motion.div
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={modalSlideDown}
          className="relative w-full max-w-4xl max-h-[80vh] flex"
          onClick={(e) => e.stopPropagation()}
          data-testid="command-palette"
        >
          {/* Main Search Panel */}
          <div className={cn(
            "flex-1 bg-glass-elevated backdrop-blur-glass rounded-2xl",
            "border border-glass shadow-elevated shadow-inset-border",
            "overflow-hidden",
            previewMode !== 'closed' ? 'rounded-r-none' : ''
          )}>
            {/* Search Input */}
            <div className="p-4 border-b border-glass">
              <div className="flex items-center gap-3">
                <div className="text-lg">🔍</div>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={source === "folder" ? "Search folders and files..." : "Search documents..."}
                  className="flex-1 bg-transparent text-text-primary placeholder-text-muted outline-none text-lg"
                  autoFocus
                  data-testid="command-palette-query"
                />
                {isLoading && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    className="w-5 h-5 border-2 border-accent-primary border-t-transparent rounded-full"
                  />
                )}
              </div>
            </div>

            {/* Results List */}
            <div className="max-h-96 overflow-y-auto">
              {results.length === 0 && !isLoading && query && (
                <div className="p-8 text-center text-text-muted">
                  <div className="text-4xl mb-2">📭</div>
                  <p>No documents match &quot;{query}&quot;</p>
                  <p className="text-sm mt-1">Try different keywords or check your indexed folders</p>
                </div>
              )}

              {results.map((result, index) => (
                <SearchResultItem
                  key={result.file_path}
                  result={result}
                  isSelected={index === selectedIndex}
                  onClick={() => handleSelectResult(result)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  onPreviewToggle={() => togglePreview(result)}
                  getFileIcon={getFileIcon}
                  dataTestId={`files-result-item-${index}`}
                />
              ))}
            </div>

            {/* Footer */}
            <div className="p-3 border-t border-glass bg-glass-elevated/50">
              <div className="flex items-center justify-between text-xs text-text-muted">
                <div className="flex items-center gap-4">
                  <span>↑↓ Navigate</span>
                  <span>↵ Open in App</span>
                  <span>␣ Preview</span>
                  <span>⌘↵ Open External</span>
                </div>
                <div>Esc to close</div>
              </div>
            </div>
          </div>

          {/* Preview Panel */}
          <AnimatePresence>
            {previewMode !== 'closed' && previewData && (
              <motion.div
                initial={{ opacity: 0, x: 20, width: 0 }}
                animate={{ opacity: 1, x: 0, width: 400 }}
                exit={{ opacity: 0, x: 20, width: 0 }}
                transition={{ duration: 0.2 }}
                className="bg-glass-elevated backdrop-blur-glass rounded-r-2xl border border-glass border-l-0 shadow-elevated overflow-hidden"
                data-testid="files-preview-pane"
              >
                <DocumentPreview
                  result={previewData}
                  mode={previewMode}
                  onClose={() => {
                    setPreviewMode('closed');
                    setPreviewData(null);
                  }}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

interface SearchResultItemProps {
  result: SearchResult;
  isSelected: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onPreviewToggle: () => void;
  getFileIcon: (fileType: string) => string;
  dataTestId?: string;
}

function SearchResultItem({
  result,
  isSelected,
  onClick,
  onMouseEnter,
  onPreviewToggle,
  getFileIcon,
  dataTestId
}: SearchResultItemProps) {
  return (
    <motion.button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      className={cn(
        "w-full text-left p-4 border-b border-glass/50 transition-colors",
        isSelected
          ? "bg-glass-hover shadow-inset-border"
          : "hover:bg-glass-hover/50"
      )}
      data-testid={dataTestId || "files-result-item"}
    >
      <div className="flex items-start gap-3">
        {/* File Icon or Thumbnail */}
        <div className="w-8 h-8 mt-1 flex-shrink-0 flex items-center justify-center">
          {result.result_type === "image" && result.thumbnail_url ? (
            <img
              src={getApiBaseUrl() + result.thumbnail_url}
              alt={result.file_name}
              className="w-full h-full object-cover rounded border border-glass"
              onError={(e) => {
                // Fallback to icon if thumbnail fails
                e.currentTarget.style.display = 'none';
                e.currentTarget.parentElement!.innerHTML = getFileIcon(result.file_type);
              }}
            />
          ) : (
            <div className="text-2xl">{getFileIcon(result.file_type)}</div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* File Name and Type */}
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-text-primary truncate">
              {result.file_name}
            </h3>
            <span className="text-xs text-text-muted uppercase px-2 py-0.5 bg-glass rounded">
              {result.file_type}
            </span>
            {result.page_number && (
              <span className="text-xs text-text-muted px-2 py-0.5 bg-accent-primary/10 rounded">
                Page {result.page_number}
              </span>
            )}
          </div>

          {/* Breadcrumb */}
          <div className="text-sm text-text-muted mb-2 truncate">
            {result.breadcrumb}
          </div>

          {/* Snippet with Highlights */}
          <div className="text-sm text-text-primary leading-relaxed">
            <HighlightedText
              text={result.snippet}
              highlights={result.highlight_offsets}
            />
          </div>

          {/* Similarity Score */}
          <div className="text-xs text-text-muted mt-2">
            Match: {(result.similarity_score * 100).toFixed(1)}%
          </div>
        </div>

        {/* Preview Toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPreviewToggle();
          }}
          className="flex-shrink-0 p-2 text-text-muted hover:text-text-primary hover:bg-glass-hover rounded transition-colors"
          title="Quick preview (Space)"
        >
          👁️
        </button>
      </div>
    </motion.button>
  );
}

interface HighlightedTextProps {
  text: string;
  highlights: [number, number][];
}

function HighlightedText({ text, highlights }: HighlightedTextProps) {
  if (!highlights || highlights.length === 0) {
    return <span>{text}</span>;
  }

  // Sort highlights by start position
  const sortedHighlights = [...highlights].sort((a, b) => a[0] - b[0]);

  const parts: { text: string; highlighted: boolean }[] = [];
  let lastEnd = 0;

  for (const [start, end] of sortedHighlights) {
    // Add non-highlighted text before this highlight
    if (start > lastEnd) {
      parts.push({
        text: text.slice(lastEnd, start),
        highlighted: false
      });
    }

    // Add highlighted text
    parts.push({
      text: text.slice(start, end),
      highlighted: true
    });

    lastEnd = end;
  }

  // Add remaining text
  if (lastEnd < text.length) {
    parts.push({
      text: text.slice(lastEnd),
      highlighted: false
    });
  }

  return (
    <>
      {parts.map((part, index) => (
        part.highlighted ? (
          <mark
            key={index}
            className="bg-accent-primary/20 text-accent-primary px-0.5 rounded"
          >
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        )
      ))}
    </>
  );
}

interface DocumentPreviewProps {
  result: SearchResult;
  mode: 'loading' | 'previewing';
  onClose: () => void;
}

function DocumentPreview({ result, mode, onClose }: DocumentPreviewProps) {
  const baseUrl = getApiBaseUrl();

  if (mode === 'loading') {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            className="w-8 h-8 border-2 border-accent-primary border-t-transparent rounded-full mx-auto mb-4"
          />
          <p className="text-text-muted">Loading preview...</p>
        </div>
      </div>
    );
  }

  const isImage = result.result_type === "image";

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-glass flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{isImage ? '🖼️' : (result.file_type === 'pdf' ? '📄' : '📝')}</span>
          <div>
            <h3 className="font-medium text-text-primary truncate max-w-64">
              {result.file_name}
            </h3>
            <p className="text-xs text-text-muted">
              {isImage ? (
                result.metadata?.width && result.metadata?.height ?
                  `${result.metadata.width} × ${result.metadata.height}px` :
                  'Image'
              ) : (
                result.page_number ? `Page ${result.page_number} of ${result.total_pages || 1}` : 'Document'
              )}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Preview Content */}
      <div className="flex-1 p-4 overflow-y-auto">
        {isImage ? (
          <div className="flex flex-col items-center">
            {result.thumbnail_url && (
              <img
                src={baseUrl + result.thumbnail_url}
                alt={result.file_name}
                className="max-w-full max-h-64 object-contain rounded-lg border border-glass mb-4"
              />
            )}
            <div className="text-center">
              <p className="text-sm text-text-primary mb-2">{result.snippet}</p>
              {result.metadata?.width && result.metadata?.height && (
                <p className="text-xs text-text-muted">
                  {result.metadata.width} × {result.metadata.height} pixels
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="prose prose-sm max-w-none">
            <HighlightedText
              text={result.snippet}
              highlights={result.highlight_offsets}
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-glass bg-glass-elevated/50">
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span>Match: {(result.similarity_score * 100).toFixed(1)}%</span>
          <span>↵ Open in app</span>
        </div>
      </div>
    </div>
  );
}
