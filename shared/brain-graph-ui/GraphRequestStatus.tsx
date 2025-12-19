import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { GraphApiDiagnostics, GraphRequestInfo } from "./types";
import { formatTimestamp } from "./utils";

type GraphRequestStatusProps = {
  requestInfo: GraphRequestInfo | null;
  error?: string | null;
  fallbackTarget: string;
  onRetry: () => void;
  apiDiagnostics?: GraphApiDiagnostics;
};

function deriveHealthUrl(fallbackTarget: string, diagnostics?: GraphApiDiagnostics) {
  if (diagnostics?.healthUrl) {
    return diagnostics.healthUrl;
  }
  const candidateOrigins: string[] = [];
  if (diagnostics?.baseUrl) {
    candidateOrigins.push(diagnostics.baseUrl);
  }
  if (fallbackTarget) {
    candidateOrigins.push(fallbackTarget);
  }
  for (const originCandidate of candidateOrigins) {
    try {
      const parsed = new URL(originCandidate);
      return `${parsed.origin}/health`;
    } catch {
      continue;
    }
  }
  return "/health";
}

function toStatusLabel(info: GraphRequestInfo | null, error?: string | null) {
  if (error) {
    return "Graph data failed to load";
  }
  if (!info) {
    return "No graph snapshot request has fired yet.";
  }
  switch (info.status) {
    case "pending":
      return "Fetching graph snapshot…";
    case "success":
      return "Latest snapshot returned 0 nodes.";
    case "error":
      return "Last request failed.";
    case "aborted":
      return "Request was aborted before it completed.";
    default:
      return "Graph snapshot idle.";
  }
}

export function GraphRequestStatus({ requestInfo, error, fallbackTarget, onRetry, apiDiagnostics }: GraphRequestStatusProps) {
  const [copied, setCopied] = useState(false);
  const resetTimerRef = useRef<number | null>(null);
  const target = requestInfo?.target ?? fallbackTarget;
  const statusLabel = toStatusLabel(requestInfo, error);
  const healthUrl = useMemo(() => deriveHealthUrl(target, apiDiagnostics), [target, apiDiagnostics]);
  const timestamp = requestInfo?.completedAt ?? requestInfo?.startedAt ?? null;
  const httpStatus = requestInfo?.httpStatus ? `${requestInfo.httpStatus}` : "—";
  const duration =
    typeof requestInfo?.durationMs === "number" ? `${Math.max(0, requestInfo.durationMs).toFixed(0)} ms` : requestInfo?.status === "pending" ? "…" : "—";

  const curlCommand = target ? `curl -s "${target}"` : "";
  const canCopy = Boolean(curlCommand);

  const handleCopy = useCallback(async () => {
    if (!canCopy) {
      return;
    }
    const useClipboard = typeof navigator !== "undefined" && navigator.clipboard?.writeText;
    const useDocument = typeof document !== "undefined";
    try {
      if (useClipboard) {
        await navigator.clipboard.writeText(curlCommand);
      } else if (useDocument) {
        const textarea = document.createElement("textarea");
        textarea.value = curlCommand;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      } else {
        throw new Error("Clipboard unavailable");
      }
      setCopied(true);
      if (resetTimerRef.current) {
        window.clearTimeout(resetTimerRef.current);
      }
      resetTimerRef.current = window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }, [canCopy, curlCommand]);

  useEffect(() => {
    return () => {
      if (resetTimerRef.current) {
        window.clearTimeout(resetTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="absolute inset-0 flex h-full flex-col justify-center gap-4 bg-slate-950/80 px-6 py-8 text-sm text-slate-200">
      <div className="space-y-1">
        <p className="text-base font-semibold text-white">{statusLabel}</p>
        {error ? <p className="text-xs text-red-400">{error}</p> : null}
        <p className="text-xs text-slate-400">
          Nodes render only after `/api/brain/universe` responds. Use the commands below to verify the backend path that this UI is calling.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-xs text-slate-300">
        <dl className="space-y-3">
          <div>
            <dt className="text-[0.65rem] uppercase tracking-[0.25em] text-slate-500">Request URL</dt>
            <dd className="break-words text-slate-100">{target || "Not computed yet"}</dd>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <dt className="text-[0.65rem] uppercase tracking-[0.25em] text-slate-500">HTTP</dt>
              <dd className="text-slate-100">{httpStatus}</dd>
            </div>
            <div>
              <dt className="text-[0.65rem] uppercase tracking-[0.25em] text-slate-500">Duration</dt>
              <dd className="text-slate-100">{duration}</dd>
            </div>
            <div>
              <dt className="text-[0.65rem] uppercase tracking-[0.25em] text-slate-500">Last attempt</dt>
              <dd className="text-slate-100">{timestamp ? formatTimestamp(timestamp) : "—"}</dd>
            </div>
          </div>
        </dl>
        {apiDiagnostics?.baseUrl ? (
          <p className="mt-3 text-[0.7rem] text-slate-400">
            API base resolved to <span className="text-slate-200">{apiDiagnostics.baseUrl}</span> ({apiDiagnostics.source}
            {apiDiagnostics.note ? `: ${apiDiagnostics.note}` : ""})
          </p>
        ) : null}
      </div>

      <div className="space-y-2 text-xs text-slate-400">
        <p className="text-[0.65rem] uppercase tracking-[0.25em] text-slate-500">Debug checklist</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Backend health: <span className="text-slate-100">curl {healthUrl}</span>
          </li>
          <li>Reload with DevTools → Network open and confirm the `/api/brain/universe` request appears.</li>
          <li>Ensure `NEXT_PUBLIC_API_URL` (or the local dev heuristic) points at the backend before hard-refreshing.</li>
        </ul>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button
          type="button"
          className="rounded-md border border-slate-600 px-3 py-1 text-slate-200 hover:border-slate-400"
          onClick={() => {
            setCopied(false);
            onRetry();
          }}
        >
          Retry
        </button>
        <button
          type="button"
          onClick={handleCopy}
          disabled={!canCopy}
          className="rounded-md border border-slate-600 px-3 py-1 text-slate-200 hover:border-slate-400 disabled:opacity-60"
        >
          {copied ? "Copied curl" : "Copy curl"}
        </button>
        {curlCommand ? <code className="break-all text-[0.65rem] text-slate-400">{curlCommand}</code> : null}
      </div>
    </div>
  );
}


