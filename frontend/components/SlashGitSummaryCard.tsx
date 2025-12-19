"use client";

import React, { useMemo as reactUseMemo } from "react";
import { SlashGitSummaryPayload, SlashGitSourceItem, SlashQueryPlan } from "@/lib/useWebSocket";
import { useToast } from "@/lib/useToast";
import { openExternalUrl, copyToClipboard } from "@/lib/externalLinks";

interface SlashGitSummaryCardProps {
  summary: SlashGitSummaryPayload;
  queryPlan?: SlashQueryPlan;
}

const SectionContainer = ({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) => {
  if (!children) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-white/50">{title}</div>
      <div className="space-y-2">{children}</div>
    </div>
  );
};

const PlanBadge = ({ label, value }: { label: string; value: string }) => (
  <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] text-white/70">
    <span className="uppercase text-[9px] tracking-wide text-white/40">{label}: </span>
    {value}
  </span>
);

const GitSourceCard = ({
  source,
  onOpen,
  onCopy,
}: {
  source: SlashGitSourceItem;
  onOpen: (url?: string) => void;
  onCopy: (url?: string) => void;
}) => {
  const defaultLabel =
    source.type === "pr"
      ? `PR #${source.pr_number ?? source.id ?? "?"}`
      : `Commit ${source.short_sha ?? source.id ?? ""}`.trim();
  const label = source.label || defaultLabel;
  const timestamp = source.timestamp ? new Date(source.timestamp) : null;
  const snippet = source.message || source.snippet;

  return (
    <div className="rounded-2xl border border-white/10 bg-black/25 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{label}</p>
          <p className="text-[11px] text-white/50">
            {source.author || "Unknown"} ·{" "}
            {timestamp && !Number.isNaN(timestamp.getTime())
              ? timestamp.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
              : "Unknown time"}
          </p>
        </div>
        {typeof source.rank === "number" && (
          <span className="text-[10px] uppercase tracking-wide text-white/40">Source {source.rank}</span>
        )}
      </div>
      {snippet && <p className="mt-2 text-sm text-white/80">{snippet}</p>}
      {source.url && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onOpen(source.url)}
            className="inline-flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-xs font-semibold text-white/80 transition hover:border-white/40 hover:text-white"
          >
            Open
            <span aria-hidden="true">↗</span>
          </button>
          <button
            type="button"
            onClick={() => onCopy(source.url)}
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1 text-[11px] font-medium text-white/70 transition hover:border-white/30 hover:text-white"
          >
            Copy link
          </button>
        </div>
      )}
    </div>
  );
};

const SlashGitSummaryCard: React.FC<SlashGitSummaryCardProps> = ({ summary, queryPlan }) => {
  const { addToast } = useToast();
  const context = summary.context || {};
  const sources = summary.sources || [];
  const graphContext = summary.graph_context || summary.data?.graph_context || {};
  const snapshot = summary.data?.snapshot || {};
  const analysisSections = Array.isArray(summary.analysis?.sections) ? summary.analysis.sections : [];
  const notablePrs = Array.isArray(summary.analysis?.notable_prs) ? summary.analysis.notable_prs : [];
  const nextActions = Array.isArray(summary.analysis?.next_actions) ? summary.analysis.next_actions : [];
  const references = Array.isArray(summary.analysis?.references) ? summary.analysis.references : [];

  const planBadges = reactUseMemo(() => {
    const badges: Array<{ label: string; value: string }> = [];
    const targets =
      queryPlan?.targets
        ?.map((target) => target.label || target.identifier || target.raw)
        .filter((target): target is string => Boolean(target)) || [];
    if (targets.length) {
      badges.push({ label: "Targets", value: targets.join(", ") });
    }
    if (queryPlan?.time_scope && typeof queryPlan.time_scope === "object") {
      const scopeLabel = (queryPlan.time_scope as Record<string, any>).label;
      if (scopeLabel && typeof scopeLabel === "string") {
        badges.push({ label: "Window", value: scopeLabel });
      }
    }
    if (queryPlan?.intent) {
      badges.push({ label: "Intent", value: queryPlan.intent });
    }
    if (queryPlan?.tone) {
      badges.push({ label: "Tone", value: queryPlan.tone });
    }
    return badges;
  }, [queryPlan]);

  const activityCounts = reactUseMemo(() => {
    const commits = Array.isArray(snapshot?.commits) ? snapshot.commits.length : graphContext?.activity_counts?.commits;
    const prs = Array.isArray(snapshot?.prs) ? snapshot.prs.length : graphContext?.activity_counts?.prs;
    if (!commits && !prs) {
      return null;
    }
    return { commits: commits ?? 0, prs: prs ?? 0 };
  }, [snapshot, graphContext]);

  const handleOpenLink = async (url?: string) => {
    if (!url) {
      addToast("Link unavailable for this source.", "warning");
      return;
    }
    const opened = openExternalUrl(url);
    if (!opened) {
      const copied = await copyToClipboard(url);
      addToast(copied ? "Couldn't open link, copied instead." : "Unable to open link.", copied ? "warning" : "error");
    }
  };

  const handleCopyLink = async (url?: string) => {
    if (!url) {
      addToast("Link unavailable for this source.", "warning");
      return;
    }
    const copied = await copyToClipboard(url);
    addToast(copied ? "Link copied to clipboard." : "Unable to copy link.", copied ? "success" : "error");
  };

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/20">
      <div className="flex flex-wrap items-center gap-2 text-xs text-white/80">
        <span className="rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
          {context.scope_label || context.repo_label || "Git activity"}
        </span>
        {context.time_window_label && (
          <span className="rounded-full bg-white/5 px-2 py-0.5">{context.time_window_label}</span>
        )}
        {context.mode && (
          <span className="rounded-full bg-white/5 px-2 py-0.5 capitalize">
            {context.mode.replace(/_/g, " ")}
          </span>
        )}
      </div>

      <p className="mt-3 text-base font-semibold leading-relaxed text-white">{summary.message}</p>

      {planBadges.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {planBadges.map((badge) => (
            <PlanBadge key={`${badge.label}-${badge.value}`} label={badge.label} value={badge.value} />
          ))}
        </div>
      )}

      {activityCounts && (
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-white/60">
          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5">
            Commits: {activityCounts.commits}
          </span>
          <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5">PRs: {activityCounts.prs}</span>
        </div>
      )}

      {Array.isArray(graphContext?.authors) && graphContext.authors.length > 0 && (
        <div className="mt-3 text-[11px] uppercase tracking-wide text-white/40">
          Authors: {graphContext.authors.join(", ")}
        </div>
      )}

      {(analysisSections.length > 0 ||
        notablePrs.length > 0 ||
        nextActions.length > 0 ||
        references.length > 0) && (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {analysisSections.length > 0 && (
            <SectionContainer title="Insights">
              {analysisSections.map((section, idx) => (
                <div key={`${section.title}-${idx}`} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="text-sm font-semibold text-white">{section.title || "Insights"}</div>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-white/80">
                    {(section.insights || []).map((insight: string, insightIdx: number) => (
                      <li key={insightIdx}>{insight}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </SectionContainer>
          )}

          {notablePrs.length > 0 && (
            <SectionContainer title="Notable PRs">
              {notablePrs.map((pr, idx) => (
                <div key={`${pr.pr_number}-${idx}`} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="text-sm font-semibold text-white">{pr.title || `PR #${pr.pr_number}`}</div>
                  {pr.summary && <p className="mt-1 text-sm text-white/70">{pr.summary}</p>}
                </div>
              ))}
            </SectionContainer>
          )}

          {nextActions.length > 0 && (
            <SectionContainer title="Next Actions">
              <ul className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-white/80">
                {nextActions.map((action, idx) => (
                  <li key={idx} className="list-disc pl-4">
                    {typeof action === "string" ? action : action.text || JSON.stringify(action)}
                  </li>
                ))}
              </ul>
            </SectionContainer>
          )}

          {references.length > 0 && (
            <SectionContainer title="References">
              <div className="flex flex-wrap gap-2">
                {references.map((reference, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleOpenLink(reference.url)}
                    className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-white/80 transition hover:border-white/30 hover:text-white"
                  >
                    {reference.label || reference.url || "Reference"}
                  </button>
                ))}
              </div>
            </SectionContainer>
          )}
        </div>
      )}

      <div className="mt-4 rounded-2xl border border-white/15 bg-white/5 p-4">
        <div className="flex items-center gap-2">
          <span className="text-xl text-white">⌘</span>
          <div>
            <p className="text-sm font-semibold text-white">Sources</p>
            <p className="text-[11px] uppercase tracking-wide text-white/50">Deep links to commits and PRs</p>
          </div>
        </div>
        {sources.length ? (
          <div className="mt-4 space-y-3">
            {sources.map((source, idx) => (
              <GitSourceCard
                key={source.id || `${source.type}-${idx}`}
                source={source}
                onOpen={handleOpenLink}
                onCopy={(url) => handleCopyLink(url, false)}
              />
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-white/60">No linked commits or PRs were found for this query.</p>
        )}
      </div>

      {summary.debug && (
        <div className="mt-3 text-[11px] uppercase tracking-wide text-white/35">
          Debug · {summary.debug.source || "git_pipeline"} · retrieved {summary.debug.retrieved_count ?? 0} item
          {summary.debug.retrieved_count === 1 ? "" : "s"} ({summary.debug.status || "WARN"})
        </div>
      )}
    </div>
  );
};

export default SlashGitSummaryCard;

