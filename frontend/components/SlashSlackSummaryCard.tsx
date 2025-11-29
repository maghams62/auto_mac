"use client";

import React from "react";
import { SlashSlackPayload, SlashSlackDecision, SlashSlackTask, SlashSlackTopic, SlashSlackQuestion, SlashSlackReference } from "@/lib/useWebSocket";
import { cn } from "@/lib/utils";

interface SlashSlackSummaryCardProps {
  summary: SlashSlackPayload;
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

const SlashSlackSummaryCard: React.FC<SlashSlackSummaryCardProps> = ({ summary }) => {
  const { message, sections = {}, context, graph } = summary;
  const channelLabel = context?.channel_label || context?.channel_name || "Slack";
  const timeLabel = context?.time_window_label;
  const mode = context?.mode;

  const hasTopics = Array.isArray(sections.topics) && sections.topics.length > 0;
  const hasDecisions = Array.isArray(sections.decisions) && sections.decisions.length > 0;
  const hasTasks = Array.isArray(sections.tasks) && sections.tasks.length > 0;
  const hasQuestions = Array.isArray(sections.open_questions) && sections.open_questions.length > 0;
  const hasReferences = Array.isArray(sections.references) && sections.references.length > 0;

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

      <p className="mt-3 text-base font-semibold text-white leading-relaxed">
        {message}
      </p>

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
    </div>
  );
};

export default SlashSlackSummaryCard;

