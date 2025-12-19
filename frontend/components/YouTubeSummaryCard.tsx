"use client";

import React, { useState } from "react";
import { YouTubePayload, YouTubeEvidenceSnippet } from "@/lib/useWebSocket";

interface YouTubeSummaryCardProps {
  payload: YouTubePayload;
}

const EvidenceList = ({ snippets }: { snippets: YouTubeEvidenceSnippet[] }) => {
  if (!snippets.length) {
    return <p className="text-sm text-white/70">No transcript snippets available.</p>;
  }
  return (
    <div className="space-y-2">
      {snippets.map((snip, idx) => (
        <div key={`${snip.start_seconds ?? idx}-${idx}`} className="rounded-lg border border-white/10 bg-white/5 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-white/50">
            {snip.timestamp || `~${snip.start_seconds?.toFixed(0)}s`}
          </div>
          <p className="mt-1 text-sm text-white/80">{snip.text || "Snippet unavailable."}</p>
        </div>
      ))}
    </div>
  );
};

export default function YouTubeSummaryCard({ payload }: YouTubeSummaryCardProps) {
  const { message, details, data } = payload;
  const video = data?.video || {};
  const traceUrl = data?.trace_url;
  const cached = data?.cached;
  const snippets = Array.isArray(data?.evidence) ? data?.evidence : [];
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/20">
      <div className="flex flex-wrap items-center gap-2 text-xs text-white/80">
        <span className="rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
          {video.title || "YouTube video"}
        </span>
        {video.channel_title && (
          <span className="rounded-full bg-white/5 px-2 py-0.5">
            {video.channel_title}
          </span>
        )}
        {cached && (
          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-200">
            Using cached transcript
          </span>
        )}
        {traceUrl && (
          <a
            href={traceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full bg-white/5 px-2 py-0.5 text-accent-primary hover:underline"
          >
            View trace
          </a>
        )}
      </div>

      <p className="mt-3 text-base font-semibold text-white leading-relaxed">
        {message}
      </p>

      {details && (
        <p className="mt-2 text-sm text-white/70 whitespace-pre-line">{details}</p>
      )}

      <div className="mt-4">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-lg border border-white/15 bg-black/20 px-3 py-2 text-sm font-semibold text-white hover:text-accent-primary"
        >
          <span>{open ? "Hide transcript evidence" : "View transcript evidence"}</span>
          <span className="text-xs uppercase tracking-wide text-white/50">{open ? "▲" : "▼"}</span>
        </button>
        {open && (
          <div className="mt-3">
            <EvidenceList snippets={snippets} />
          </div>
        )}
      </div>
    </div>
  );
}

