import type { Meta, StoryObj } from "@storybook/react";
import { useEffect } from "react";

import { ImpactAlertsPanel } from "./impact-alerts-panel";

const mockDocIssues = [
  {
    id: "story-github-alert",
    doc_title: "Payments doc drift",
    doc_path: "docs/payments.md",
    impact_level: "high",
    summary: "Latest payments rollout diverged from docs.",
    repo_id: "docs-platform",
    github_url: "https://github.com/example/impact/pull/42",
    detected_at: "2024-10-21T12:00:00.000Z",
  },
  {
    id: "story-slack-alert",
    doc_title: "On-call runbook complaint",
    doc_path: "runbooks/oncall.md",
    impact_level: "low",
    summary: "Slack escalation pointed to missing steps.",
    repo_id: "docs-platform",
    slack_url: "https://slack.com/example-thread",
    detected_at: "2024-10-22T15:20:00.000Z",
  },
];

const MockedImpactAlertsPanel = () => {
  useEffect(() => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (typeof input === "string" && input.startsWith("/api/impact/doc-issues")) {
        return new Response(
          JSON.stringify({ doc_issues: mockDocIssues, mode: "synthetic", fallback: false }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ) as Response;
      }
      if (originalFetch) {
        return originalFetch(input, init);
      }
      throw new Error("Unhandled fetch call in ImpactAlertsPanel story");
    }) as typeof fetch;

    return () => {
      if (originalFetch) {
        globalThis.fetch = originalFetch;
      }
    };
  }, []);

  return <ImpactAlertsPanel />;
};

const meta: Meta<typeof ImpactAlertsPanel> = {
  title: "Impact/ImpactAlertsPanel",
  component: ImpactAlertsPanel,
  parameters: {
    layout: "fullscreen",
  },
};

export default meta;
type Story = StoryObj<typeof ImpactAlertsPanel>;

export const LiveDataMock: Story = {
  render: () => <MockedImpactAlertsPanel />,
};


