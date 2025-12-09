"use client";

import React, { useState } from "react";
import {
  SlashSlackPayload,
  SlashSlackDecision,
  SlashSlackTask,
  SlashSlackTopic,
  SlashSlackQuestion,
  SlashSlackReference,
  SlashQueryPlan,
  SlackSourceItem,
} from "@/lib/useWebSocket";
import { useToast } from "@/lib/useToast";
import { openExternalUrl, copyToClipboard } from "@/lib/externalLinks";

interface SlashSlackSummaryCardProps {
  summary: SlashSlackPayload;
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
      <div className="text-xs font-semibold uppercase tracking-wide text-white/50">
        {title}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
};

const TopicCard = ({ topic }: { topic: SlashSlackTopic }) => (
  <div className="rounded-xl border border-white/10 bg-white/5 p-3">
    <div className="text-sm font-semibold text-white">{topic.topic}</div>
    {topic.sample && (
      <p className="mt-1 text-xs text-white/60 line-clamp-3">{topic.sample}</p>
    )}
    {typeof topic.mentions === "number" && (
      <div className="mt-2 text-[10px] uppercase tracking-wide text-white/50">
        {topic.mentions} mention{topic.mentions === 1 ? "" : "s"}
      </div>
    )}
  </div>
);

const DecisionCard = ({ decision }: { decision: SlashSlackDecision }) => (
  <div className="rounded-xl border border-success-border/30 bg-success-bg/10 p-3">
    <div className="text-sm font-semibold text-white">{decision.text}</div>
    <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-white/60">
      {decision.participant && (
        <span className="rounded-full bg-white/10 px-2 py-0.5">
          {decision.participant}
        </span>
      )}
      {decision.timestamp && (
        <span className="rounded-full bg-white/10 px-2 py-0.5">
          {new Date(parseFloat(decision.timestamp) * 1000).toLocaleString()}
        </span>
      )}
      {decision.permalink && (
        <a
          href={decision.permalink}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full bg-white/5 px-2 py-0.5 text-accent-primary hover:underline"
        >
          View thread
        </a>
      )}
    </div>
  </div>
);

const TaskCard = ({ task }: { task: SlashSlackTask }) => (
  <div className="rounded-xl border border-warning-border/30 bg-warning-bg/5 p-3">
    <div className="text-sm font-medium text-white">{task.description}</div>
    <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-white/60">
      {task.assignee && (
        <span className="rounded-full bg-white/10 px-2 py-0.5">
          {task.assignee}
        </span>
      )}
      {task.timestamp && (
        <span className="rounded-full bg-white/10 px-2 py-0.5">
          Logged {new Date(parseFloat(task.timestamp) * 1000).toLocaleDateString()}
        </span>
      )}
      {task.permalink && (
        <a
          href={task.permalink}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full bg-white/5 px-2 py-0.5 text-accent-primary hover:underline"
        >
          Jump to message
        </a>
      )}
    </div>
  </div>
);

const QuestionCard = ({ question }: { question: SlashSlackQuestion }) => (
  <div className="rounded-xl border border-white/10 bg-white/5 p-3">
    <div className="text-sm font-medium text-white">{question.text}</div>
    <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-white/60">
      {question.participant && (
        <span className="rounded-full bg-white/10 px-2 py-0.5">
          {question.participant}
        </span>
      )}
      {question.permalink && (
        <a
          href={question.permalink}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full bg-white/5 px-2 py-0.5 text-accent-primary hover:underline"
        >
          View context
        </a>
      )}
    </div>
  </div>
);

const ReferenceChip = ({ reference }: { reference: SlashSlackReference }) => (
  <a
    href={reference.url}
    target="_blank"
    rel="noopener noreferrer"
    className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-white/80 hover:border-white/30"
  >
    <span className="text-[10px] uppercase tracking-wide text-white/50">
      {reference.kind}
    </span>
    <span className="max-w-[220px] truncate">{reference.url}</span>
  </a>
);

const SlackHintFooter = ({ graph }: { graph?: Record<string, any> }) => {
  if (!graph) return null;
  const nodeCount = Array.isArray(graph.nodes) ? graph.nodes.length : 0;
  const edgeCount = Array.isArray(graph.edges) ? graph.edges.length : 0;
  if (!nodeCount && !edgeCount) return null;
  return (
    <div className="text-[11px] text-white/40">
      Graph payload ready — {nodeCount} node{nodeCount === 1 ? "" : "s"}, {edgeCount} edge{edgeCount === 1 ? "" : "s"}.
    </div>
  );
};

const PlanBadge = ({ label, value }: { label: string; value: string }) => (
  <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] text-white/70">
    <span className="uppercase text-[9px] tracking-wide text-white/40">{label}: </span>
    {value}
  </span>
);

const SlackSourcesSection = ({
  sources,
  scopeLabels,
  emptyCopy,
  onOpen,
  onCopy,
}: {
  sources: SlackSourceItem[];
  scopeLabels: string[];
  emptyCopy: string;
  onOpen: (source: SlackSourceItem) => void;
  onCopy: (permalink?: string) => void;
}) => {
  const hasSources = sources.length > 0;
  return (
    <div className="mt-4 rounded-2xl border border-white/15 bg-white/5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xl text-[#36C5F0]">#</span>
          <div>
            <p className="text-sm font-semibold text-white">Sources from Slack</p>
            <p className="text-[11px] uppercase tracking-wide text-white/50">Click to open in Slack</p>
          </div>
        </div>
        {scopeLabels.length > 0 && (
          <span className="rounded-full border border-white/15 bg-white/10 px-2 py-0.5 text-[11px] text-white/70">
            Scoped to {scopeLabels.join(", ")}
          </span>
        )}
      </div>
      {hasSources ? (
        <div className="mt-4 space-y-3">
          {sources.map((source, idx) => (
            <SlackSourceCard key={source.id || `${source.channel}-${idx}`} source={source} onOpen={onOpen} onCopy={onCopy} />
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-white/60">{emptyCopy}</p>
      )}
    </div>
  );
};

const SlackSourceCard = ({
  source,
  onOpen,
  onCopy,
}: {
  source: SlackSourceItem;
  onOpen: (source: SlackSourceItem) => void;
  onCopy: (permalink?: string) => void;
}) => {
  const formattedTime = formatSlackTimestamp(source.iso_time, source.ts);
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{source.channel || "Slack"}</p>
          <p className="text-[11px] text-white/50">
            {source.author || "Unknown"} · {formattedTime}
          </p>
        </div>
        {source.rank && (
          <span className="text-[10px] uppercase tracking-wide text-white/40">Source {source.rank}</span>
        )}
      </div>
      {source.snippet && <p className="mt-2 text-sm text-white/80">{source.snippet}</p>}
      {source.permalink && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onOpen(source)}
            className="inline-flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-xs font-semibold text-white/80 transition hover:border-white/40 hover:text-white"
          >
            Open in Slack
            <span aria-hidden="true">↗</span>
          </button>
          <button
            type="button"
            onClick={() => onCopy(source.permalink)}
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1 text-[11px] font-medium text-white/70 transition hover:border-white/30 hover:text-white"
          >
            Copy link
          </button>
        </div>
      )}
    </div>
  );
};

function formatSlackTimestamp(isoTime?: string, ts?: string): string {
  if (isoTime) {
    const date = new Date(isoTime);
    if (!isNaN(date.getTime())) {
      return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    }
  }
  if (ts) {
    const numeric = parseFloat(ts);
    if (!Number.isNaN(numeric)) {
      const date = new Date(numeric * 1000);
      if (!isNaN(date.getTime())) {
        return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
      }
    }
  }
  return "Unknown time";
}

const SlashSlackSummaryCard: React.FC<SlashSlackSummaryCardProps> = ({ summary, queryPlan }) => {
  const { addToast } = useToast();
  const { message, sections = {}, context, graph, debug } = summary;
  const channelLabel = context?.channel_label || context?.channel_name || "Slack";
  const timeLabel = context?.time_window_label;
  const mode = context?.mode;
  const [showEvidence, setShowEvidence] = useState(false);
  const planTargets =
    queryPlan?.targets
      ?.map((target) => target.label || target.identifier || target.raw)
      .filter((target): target is string => Boolean(target)) || [];
  const scopeLabels = Array.isArray(context?.channel_scope_labels)
    ? (context?.channel_scope_labels as string[])
    : [];
  const sources = summary.sources || [];
  const sourceEmptyCopy = scopeLabels.length
    ? `No Slack messages found for this query in ${scopeLabels.join(", ")}.`
    : "No Slack messages found for this query.";
  const planBadges: Array<{ label: string; value: string }> = [];
  if (planTargets.length) {
    planBadges.push({ label: "Targets", value: planTargets.join(", ") });
  }
  if (queryPlan?.time_scope && typeof queryPlan.time_scope === "object") {
    const scopeLabel = (queryPlan.time_scope as Record<string, any>).label;
    if (scopeLabel && typeof scopeLabel === "string") {
      planBadges.push({ label: "Window", value: scopeLabel });
    }
  }
  if (queryPlan?.tone) {
    planBadges.push({ label: "Tone", value: queryPlan.tone });
  }
  if (queryPlan?.intent) {
    planBadges.push({ label: "Intent", value: queryPlan.intent });
  }

  const hasTopics = Array.isArray(sections.topics) && sections.topics.length > 0;
  const hasDecisions = Array.isArray(sections.decisions) && sections.decisions.length > 0;
  const hasTasks = Array.isArray(sections.tasks) && sections.tasks.length > 0;
  const hasQuestions = Array.isArray(sections.open_questions) && sections.open_questions.length > 0;
  const hasReferences = Array.isArray(sections.references) && sections.references.length > 0;
  const sampleEvidence = Array.isArray(debug?.sample_evidence) ? debug?.sample_evidence : [];
  const retrievedCount = typeof debug?.retrieved_count === "number" ? debug?.retrieved_count : null;
  const canShowEvidence = Boolean(debug && (sampleEvidence.length > 0 || retrievedCount !== null));

  const handleOpenSource = (source: SlackSourceItem) => {
    const targetUrl = source.deep_link || source.permalink;
    if (!targetUrl) {
      addToast("Slack permalink unavailable for this source.", "warning");
      return;
    }
    const opened = openExternalUrl(targetUrl);
    if (!opened && source.permalink && source.permalink !== targetUrl) {
      const fallbackOpened = openExternalUrl(source.permalink);
      if (fallbackOpened) {
        return;
      }
    }
    if (!opened) {
      addToast("Unable to open Slack link. Copied to clipboard instead.", "warning");
      void handleCopyLink(source.permalink, true);
    }
  };

  const handleCopyLink = async (permalink?: string, silent?: boolean) => {
    if (!permalink) {
      if (!silent) {
        addToast("Slack permalink unavailable for this source.", "warning");
      }
      return;
    }
    const copied = await copyToClipboard(permalink);
    if (copied) {
      if (!silent) {
        addToast("Slack link copied to clipboard.", "success");
      }
      return;
    }
    if (!silent) {
      addToast("Unable to copy Slack link.", "error");
    }
  };

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/20">
      <div className="flex flex-wrap items-center gap-2 text-xs text-white/80">
        <span className="rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
          {channelLabel}
        </span>
        {timeLabel && (
          <span className="rounded-full bg-white/5 px-2 py-0.5">{timeLabel}</span>
        )}
        {mode && (
          <span className="rounded-full bg-white/5 px-2 py-0.5 capitalize">{mode.replace("_", " ")}</span>
        )}
      </div>

      <p className="mt-3 text-base font-semibold text-white leading-relaxed">{message}</p>

      {planBadges.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {planBadges.map((badge) => (
            <PlanBadge key={`${badge.label}-${badge.value}`} label={badge.label} value={badge.value} />
          ))}
        </div>
      )}

      <SlackSourcesSection
        sources={sources}
        scopeLabels={scopeLabels}
        emptyCopy={sourceEmptyCopy}
        onOpen={handleOpenSource}
        onCopy={handleCopyLink}
      />

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {hasTopics && (
          <SectionContainer title="Topics & Themes">
            {sections.topics?.map((topic) => (
              <TopicCard key={topic.topic} topic={topic} />
            ))}
          </SectionContainer>
        )}

        {hasDecisions && (
          <SectionContainer title="Decisions">
            {sections.decisions?.map((decision, idx) => (
              <DecisionCard key={`${decision.timestamp}-${idx}`} decision={decision} />
            ))}
          </SectionContainer>
        )}

        {hasTasks && (
          <SectionContainer title="Tasks & Follow-ups">
            {sections.tasks?.map((task, idx) => (
              <TaskCard key={`${task.timestamp}-${idx}`} task={task} />
            ))}
          </SectionContainer>
        )}

        {hasQuestions && (
          <SectionContainer title="Open Questions">
            {sections.open_questions?.map((question, idx) => (
              <QuestionCard key={`${question.timestamp}-${idx}`} question={question} />
            ))}
          </SectionContainer>
        )}
      </div>

      {hasReferences && (
        <div className="mt-4 space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-white/50">
            References
          </div>
          <div className="flex flex-wrap gap-2">
            {sections.references?.map((reference, idx) => (
              <ReferenceChip key={`${reference.url}-${idx}`} reference={reference} />
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 text-xs text-white/50">
        <SlackHintFooter graph={graph} />
      </div>

      {canShowEvidence && (
        <div className="mt-4 rounded-xl border border-white/15 bg-black/20 p-3">
          <button
            type="button"
            onClick={() => setShowEvidence((prev) => !prev)}
            className="flex w-full items-center justify-between text-left text-sm font-semibold text-white hover:text-accent-primary"
          >
            <span>{showEvidence ? "Hide evidence" : "View evidence"}</span>
            <span className="text-xs uppercase tracking-wide text-white/50">
              {showEvidence ? "▲" : "▼"}
            </span>
          </button>
          <div className="mt-1 text-[11px] text-white/50">
            {retrievedCount !== null && (
              <span>
                {retrievedCount} message{retrievedCount === 1 ? "" : "s"} scanned
              </span>
            )}
            {retrievedCount !== null && debug?.status && " • "}
            {debug?.status && <span>Status: {debug.status}</span>}
            {!retrievedCount && !debug?.status && <span>Evidence mode enabled</span>}
          </div>
          {showEvidence && (
            <div className="mt-3 space-y-3">
              {sampleEvidence.length > 0 ? (
                sampleEvidence.map((entry, idx) => (
                  <div key={`${entry.channel || "channel"}-${idx}`} className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-white/50">
                      {entry.channel || "Channel"}
                    </div>
                    <p className="mt-1 text-sm text-white/80">{entry.snippet || "Snippet unavailable."}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-white/70">No snippet captured for this result, but evidence metadata is available.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SlashSlackSummaryCard;
