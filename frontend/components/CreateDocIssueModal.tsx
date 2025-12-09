"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { overlayFade, modalSlideDown } from "@/lib/motion";
import { getApiBaseUrl } from "@/lib/apiConfig";
import { useToast } from "@/lib/useToast";
import type { EvidenceItem } from "@/lib/useWebSocket";

interface CreateDocIssueModalProps {
  isOpen: boolean;
  onClose: () => void;
  investigationId?: string;
  componentIds?: string[];
  evidence?: EvidenceItem[];
  defaultSummary?: string;
}

const SEVERITY_OPTIONS = ["high", "medium", "low"];

export function CreateDocIssueModal({
  isOpen,
  onClose,
  investigationId,
  componentIds = [],
  evidence = [],
  defaultSummary = "",
}: CreateDocIssueModalProps) {
  const apiBaseUrl = getApiBaseUrl();
  const { addToast } = useToast();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState(defaultSummary);
  const [severity, setSeverity] = useState("medium");
  const [docPath, setDocPath] = useState("");
  const [componentInput, setComponentInput] = useState(componentIds.join(", "));
  const [repoId, setRepoId] = useState("");
  const [docUrl, setDocUrl] = useState("");
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const evidenceChoices = useMemo(() => {
    if (!Array.isArray(evidence)) return [];
    return evidence
      .map((item, index) => ({
        id: item.evidence_id || `evidence-${index}`,
        label: item.title || item.url || item.source || `evidence-${index + 1}`,
      }))
      .filter((item) => Boolean(item.id));
  }, [evidence]);

  useEffect(() => {
    if (!isOpen) return;
    document.body.style.overflow = "hidden";
    setSummary(defaultSummary);
    setTitle(defaultSummary.split("\n")[0]?.slice(0, 80) ?? "");
    setComponentInput(componentIds.join(", "));
    setSelectedEvidenceIds(evidenceChoices.map((choice) => choice.id));
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen, defaultSummary, componentIds, evidenceChoices]);

  if (!isOpen) {
    return null;
  }

  const handleEvidenceToggle = (id: string) => {
    setSelectedEvidenceIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isSubmitting) return;

    const normalizedComponents = componentInput
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    if (!docPath.trim()) {
      addToast("Doc path is required", "error", 4000);
      return;
    }

    if (normalizedComponents.length === 0) {
      addToast("At least one component ID is required", "error", 4000);
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${apiBaseUrl}/traceability/doc-issues`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title || summary.slice(0, 80) || "Traceability doc issue",
          summary,
          severity,
          doc_path: docPath,
          repo_id: repoId || undefined,
          doc_url: docUrl || undefined,
          component_ids: normalizedComponents,
          origin_investigation_id: investigationId,
          evidence_ids: selectedEvidenceIds,
        }),
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        const detail = errorPayload.detail || `Request failed (${response.status})`;
        throw new Error(detail);
      }

      addToast("Doc issue created in dashboard", "success", 4000);
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create doc issue";
      addToast(message, "error", 5000);
    } finally {
      setIsSubmitting(false);
    }
  };

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
        <div className="absolute inset-0 bg-black/70 backdrop-blur" />
        <motion.div
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={modalSlideDown}
          className="relative w-full max-w-2xl rounded-2xl border border-white/10 bg-gradient-to-br from-neutral-900/95 via-neutral-850/95 to-neutral-900/95 p-6 text-white shadow-2xl"
          onClick={(event) => event.stopPropagation()}
        >
          <header className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Create doc issue</h2>
              {investigationId ? (
                <p className="text-xs text-white/60">Evidence from investigation {investigationId}</p>
              ) : null}
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1 text-white/60 transition hover:bg-white/10 hover:text-white"
              aria-label="Close"
            >
              ✕
            </button>
          </header>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="text-xs uppercase tracking-wide text-white/60">Title</label>
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Impact summary"
              />
            </div>

            <div>
              <label className="text-xs uppercase tracking-wide text-white/60">Summary</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
                rows={4}
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                placeholder="Describe the doc drift or action needed"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs uppercase tracking-wide text-white/60">Severity</label>
                <select
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
                  value={severity}
                  onChange={(event) => setSeverity(event.target.value)}
                >
                  {SEVERITY_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs uppercase tracking-wide text-white/60">Doc path</label>
                <input
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
                  value={docPath}
                  onChange={(event) => setDocPath(event.target.value)}
                  placeholder="docs/payments_api.md"
                  required
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs uppercase tracking-wide text-white/60">Component IDs</label>
                <input
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
                  value={componentInput}
                  onChange={(event) => setComponentInput(event.target.value)}
                  placeholder="comp:payments, comp:docs"
                />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wide text-white/60">Repo (optional)</label>
                <input
                  className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
                  value={repoId}
                  onChange={(event) => setRepoId(event.target.value)}
                  placeholder="service-payments"
                />
              </div>
            </div>

            <div>
              <label className="text-xs uppercase tracking-wide text-white/60">Doc URL (optional)</label>
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
                value={docUrl}
                onChange={(event) => setDocUrl(event.target.value)}
                placeholder="https://docs.example.com/payments"
              />
            </div>

            {evidenceChoices.length ? (
              <div>
                <label className="text-xs uppercase tracking-wide text-white/60">Evidence</label>
                <div className="mt-2 space-y-2 rounded-xl border border-white/10 bg-white/5 p-3">
                  {evidenceChoices.map((choice) => (
                    <label key={choice.id} className="flex items-center gap-2 text-sm text-white/80">
                      <input
                        type="checkbox"
                        className="rounded border-white/20 bg-transparent"
                        checked={selectedEvidenceIds.includes(choice.id)}
                        onChange={() => handleEvidenceToggle(choice.id)}
                      />
                      <span className="truncate">{choice.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/70 transition hover:border-white/30 hover:text-white"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-xl bg-white/90 px-4 py-2 text-sm font-semibold text-neutral-900 transition hover:bg-white"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Creating..." : "Create issue"}
              </button>
            </div>
          </form>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

