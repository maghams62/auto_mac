import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { IssueList } from "../issue-list";
import type { DocIssue } from "@/lib/types";

const baseIssue: DocIssue = {
  id: "issue-test",
  projectId: "project_test",
  componentId: "comp:test",
  repoId: "repo:test",
  docPath: "docs/test.md",
  title: "Test issue",
  summary: "Docs are out of date.",
  severity: "medium",
  status: "open",
  detectedAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  suggestedFixes: [],
  linkedCode: [],
  divergenceSources: ["docs"],
  signals: {
    gitChurn: 0,
    ticketsMentioned: 0,
    slackMentions: 0,
    supportMentions: 0,
  },
};

describe("IssueList", () => {
  it("renders reasoning path button when brainTraceUrl is present", () => {
    render(
      <IssueList
        issues={[
          {
            ...baseIssue,
            brainTraceUrl: "/brain/trace/mock",
          },
        ]}
        onSelect={() => {}}
      />,
    );

    expect(screen.getByText(/View reasoning path/i)).toBeInTheDocument();
  });
});

