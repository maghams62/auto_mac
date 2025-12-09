import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import MessageBubble from "@/components/MessageBubble";
import { Message } from "@/lib/useWebSocket";
import { ToastProvider } from "@/lib/useToast";

vi.mock("@/components/CollapsibleMessage", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="collapsible-message">{children}</div>,
}));

function renderWithProviders(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

describe("MessageBubble reasoning links", () => {
  const baseMessage: Message = {
    type: "assistant",
    message: "Here is the answer.",
    timestamp: "2025-01-01T00:00:00Z",
  };
  const slackPayload = {
    type: "slash_slack_summary" as const,
    message: "Summary for #incidents.",
    sources: [
      {
        channel: "#incidents",
        channel_id: "C123",
        author: "alice",
        iso_time: "2025-01-01T11:00:00Z",
        permalink: "https://example.slack.com/archives/C123/p123456000",
        snippet: "Important update from incidents.",
      },
    ],
  };
  const gitPayload = {
    type: "slash_git_summary" as const,
    message: "Core API saw 2 commits recently.",
    context: { repo_label: "core-api", scope_label: "Core API", time_window_label: "recent activity" },
    sources: [
      {
        id: "commit-1",
        type: "commit",
        label: "Docs portal drift evidence",
        short_sha: "abc1234",
        author: "alice",
        timestamp: "2025-11-24T10:00:00Z",
        message: "feat: add billing hooks",
        snippet: "Docs portal still references legacy VAT payload.",
        url: "https://github.com/acme/core-api/commit/abc1234",
      },
    ],
    data: { snapshot: { commits: [{ sha: "abc1234" }], prs: [] } },
  };
  const cerebrosPayload = {
    type: "slash_cerebros_summary" as const,
    message: "Cross-source insights for billing checkout.",
    context: { modalities_used: ["slack", "git"], total_results: 3 },
    sources: [
      {
        type: "slack",
        label: "#incidents thread",
        url: "https://workspace.slack.com/archives/C123/p999",
        snippet: "Ops reported repeated checkout failures.",
      },
    ],
    cerebros_answer: {
      answer: "Checkout errors driven by VAT rollout code path.",
      option: "activity_graph",
      doc_priorities: [
        { doc_id: "DOC-1", doc_title: "Checkout guide", doc_url: "https://docs/checkout", score: 0.9, reason: "Outdated VAT steps", severity: "high" },
      ],
    },
  };

  it("renders reasoning path and universe links when URLs are present", () => {
    renderWithProviders(
      <MessageBubble
        index={0}
        message={{
          ...baseMessage,
          brainTraceUrl: "/brain/trace/q-123",
          brainUniverseUrl: "/brain/universe",
        }}
      />
    );

    expect(screen.getByRole("link", { name: /View reasoning path/i })).toHaveAttribute("href", "/brain/trace/q-123");
    expect(screen.getByRole("link", { name: /Open in Brain Universe/i })).toHaveAttribute("href", "/brain/universe");
  });

  it("omits buttons when URLs are missing", () => {
    renderWithProviders(<MessageBubble index={0} message={baseMessage} />);
    expect(screen.queryByRole("link", { name: /View reasoning path/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /Open in Brain Universe/i })).toBeNull();
  });

  it("renders youtube meta and references when details are present", () => {
    renderWithProviders(
      <MessageBubble
        index={0}
        message={{
          ...baseMessage,
          command: "youtube",
          details: "Synthesized 1 source into 42 words.\n\n- (~0:30) Intro to mixtures",
        }}
      />
    );
    expect(screen.getByText(/Synthesized 1 source/i)).toBeInTheDocument();
    expect(screen.getByText(/Intro to mixtures/i)).toBeInTheDocument();
  });

  it("renders Slack quick link tile when slash_slack sources exist", () => {
    renderWithProviders(
      <MessageBubble
        index={0}
        message={{
          ...baseMessage,
          slash_slack: slackPayload,
        }}
      />
    );
    expect(screen.getAllByText(/Slack conversation/i)[0]).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open Slack conversation/i })).toBeInTheDocument();
  });

  it("renders slash git summary card when slash_git payload exists", () => {
    renderWithProviders(
      <MessageBubble
        index={0}
        message={{
          ...baseMessage,
          slash_git: gitPayload,
        }}
      />
    );
    expect(screen.getByText(/Core API saw 2 commits recently/i)).toBeInTheDocument();
    expect(screen.getByText(/Docs portal drift evidence/i)).toBeInTheDocument();
  });

  it("renders slash cerebros summary card when payload exists", () => {
    renderWithProviders(
      <MessageBubble
        index={0}
        message={{
          ...baseMessage,
          slash_cerebros: cerebrosPayload,
        }}
      />
    );
    expect(screen.getByText(/Checkout errors driven by VAT rollout code path/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Open/i }).length).toBeGreaterThan(0);
  });
});

