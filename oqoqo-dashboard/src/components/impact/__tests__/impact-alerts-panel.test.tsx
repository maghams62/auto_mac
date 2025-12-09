import type { ReactNode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ImpactAlertsPanel } from "@/components/impact/impact-alerts-panel";
import { impactAlertsCopy } from "@/lib/mock-impact-alerts";

vi.mock("@/components/ui/select", () => {
  const PassThrough = ({ children }: { children?: ReactNode }) => <>{children}</>;
  const SelectValue = ({ placeholder, children }: { placeholder?: ReactNode; children?: ReactNode }) => (
    <span>{children ?? placeholder}</span>
  );

  return {
    Select: PassThrough,
    SelectTrigger: PassThrough,
    SelectContent: PassThrough,
    SelectItem: PassThrough,
    SelectValue,
  };
});

const mockIssues = [
  {
    id: "issue-github-only",
    doc_title: "Payments doc drift",
    doc_path: "docs/payments.md",
    impact_level: "high",
    summary: "Payments doc needs updates.",
    detected_at: "2024-05-01T12:00:00.000Z",
    github_url: "https://github.com/example/impact/pr/42",
  },
  {
    id: "issue-slack-only",
    doc_title: "On-call runbook complaint",
    doc_path: "docs/oncall.md",
    impact_level: "low",
    summary: "Slack thread flagged missing runbook steps.",
    detected_at: "2024-05-01T13:00:00.000Z",
    slack_url: "https://slack.com/example-thread",
  },
];

const jsonResponse = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

describe("ImpactAlertsPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("renders fetched rows with conditional deep links for live data", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse({ status: "OK", data: { doc_issues: mockIssues, mode: "atlas", fallback: false } }),
    );

    render(<ImpactAlertsPanel />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/impact/doc-issues?source=impact-report&mode=synthetic",
        expect.objectContaining({ cache: "no-store" }),
      );
    });

    const alertRows = await screen.findAllByText(/Alert ID •/i);
    expect(alertRows).toHaveLength(2);
    expect(screen.getByText("Payments doc drift")).toBeInTheDocument();
    expect(screen.getByText("On-call runbook complaint")).toBeInTheDocument();
    expect(screen.getByText("Live data")).toBeInTheDocument();

    const prLinks = screen.getAllByRole("link", { name: "View PR" });
    expect(prLinks).toHaveLength(1);
    expect(prLinks[0]).toHaveAttribute("href", mockIssues[0].github_url);

    const slackLinks = screen.getAllByRole("link", { name: "View Slack thread" });
    expect(slackLinks).toHaveLength(1);
    expect(slackLinks[0]).toHaveAttribute("href", mockIssues[1].slack_url);
  });

  test("shows synthetic fallback badge when upstream falls back", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse({ status: "UNAVAILABLE", fallbackReason: "synthetic_fallback", data: { doc_issues: [], mode: "synthetic", fallback: true } }),
    );

    render(<ImpactAlertsPanel />);

    await waitFor(() => {
      expect(screen.getByText("Synthetic fallback")).toBeInTheDocument();
    });
    expect(screen.getByText(impactAlertsCopy.empty)).toBeInTheDocument();
  });

  test("renders error state when request fails", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("upstream boom", { status: 500, headers: { "Content-Type": "text/plain" } }),
    );
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(<ImpactAlertsPanel />);

    await waitFor(() => {
      expect(screen.getByText(impactAlertsCopy.error)).toBeInTheDocument();
    });
  });
});


