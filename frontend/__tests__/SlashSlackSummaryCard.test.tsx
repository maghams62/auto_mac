import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SlashSlackSummaryCard from "@/components/SlashSlackSummaryCard";
import { SlashSlackPayload } from "@/lib/useWebSocket";
import { ToastProvider } from "@/lib/useToast";

const buildPayload = (overrides: Partial<SlashSlackPayload> = {}): SlashSlackPayload => ({
  type: "slash_slack_summary",
  message: "In #all-cerebros we covered VAT doc drift.",
  context: {
    channel_label: "#all-cerebros",
    mode: "channel_recap",
    time_window_label: "last 3 days",
  },
  sections: {
    topics: [
      {
        topic: "VAT drift",
        sample: "Docs lag behind new VAT rules.",
      },
    ],
  },
  debug: {
    source: "live_slack",
    retrieved_count: 5,
    status: "PASS",
    sample_evidence: [
      {
        channel: "#all-cerebros",
        snippet: "Docs still say VAT checks are EU-only but code enforces UK values.",
      },
    ],
  },
  ...overrides,
});

const renderWithToast = (ui: React.ReactNode) => render(<ToastProvider>{ui}</ToastProvider>);

describe("SlashSlackSummaryCard", () => {
  it("toggles evidence visibility without leaking JSON", () => {
    renderWithToast(<SlashSlackSummaryCard summary={buildPayload()} />);

    const toggle = screen.getByRole("button", { name: /view evidence/i });
    expect(toggle).toBeInTheDocument();
    expect(screen.queryByText(/Docs still say VAT checks/i)).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: /hide evidence/i })).toBeInTheDocument();
    expect(screen.getByText(/Docs still say VAT checks/i)).toBeInTheDocument();
  });

  it("renders Slack sources with deep link controls", async () => {
    const user = userEvent.setup();
    const payload = buildPayload({
      sources: [
        {
          id: "src-1",
          channel: "#core-api",
          author: "alice",
          snippet: "Deploy completed successfully.",
          iso_time: new Date("2025-01-01T10:00:00Z").toISOString(),
          permalink: "https://example.slack.com/archives/C123/p1700000000000001",
          deep_link: "slack://channel?team=T123&id=C123&message=1700000000000001",
          rank: 1,
        },
      ],
      context: {
        channel_scope_labels: ["#core-api"],
      },
    });
    const openSpy = vi.spyOn(window, "open").mockReturnValue(window);
    renderWithToast(<SlashSlackSummaryCard summary={payload} />);

    expect(screen.getByText(/Sources from Slack/i)).toBeInTheDocument();
    expect(screen.getByText(/Deploy completed successfully/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /open in slack/i }));
    expect(openSpy).toHaveBeenCalledWith("slack://channel?team=T123&id=C123&message=1700000000000001", "_blank", "noopener,noreferrer");
    openSpy.mockRestore();
  });

  it("copies Slack link when copy button pressed", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    const payload = buildPayload({
      sources: [
        {
          id: "src-2",
          channel: "#billing",
          author: "bob",
          snippet: "Updated billing doc is live.",
          iso_time: new Date("2025-02-02T12:00:00Z").toISOString(),
          permalink: "https://example.slack.com/archives/C999/p1700001111111111",
          rank: 1,
        },
      ],
    });
    renderWithToast(<SlashSlackSummaryCard summary={payload} />);
    await user.click(screen.getByRole("button", { name: /copy link/i }));
    expect(writeText).toHaveBeenCalledWith("https://example.slack.com/archives/C999/p1700001111111111");
  });
});

