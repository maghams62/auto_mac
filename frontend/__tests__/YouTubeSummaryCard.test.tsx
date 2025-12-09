import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import YouTubeSummaryCard from "@/components/YouTubeSummaryCard";
import { YouTubePayload } from "@/lib/useWebSocket";

const buildPayload = (overrides: Partial<YouTubePayload> = {}): YouTubePayload => ({
  type: "youtube_summary",
  status: "success",
  message: "This video argues focused practice beats 10,000 hours.",
  details: "(Using cached transcript)",
  data: {
    video: {
      title: "Learning Fast",
      channel_title: "Cerebros",
    },
    evidence: [
      { timestamp: "0:30", text: "Key claim about 20-hour practice." },
    ],
    trace_url: "/brain/trace/yt-123",
    cached: true,
  },
  ...overrides,
});

describe("YouTubeSummaryCard", () => {
  it("renders summary and toggles evidence", () => {
    render(<YouTubeSummaryCard payload={buildPayload()} />);

    expect(screen.getByText(/Learning Fast/)).toBeInTheDocument();
    expect(screen.getByText(/This video argues focused practice/)).toBeInTheDocument();
    expect(screen.getAllByText(/Using cached transcript/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /View trace/i })).toHaveAttribute("href", "/brain/trace/yt-123");

    const toggle = screen.getByRole("button", { name: /view transcript evidence/i });
    fireEvent.click(toggle);
    expect(screen.getByText(/Key claim about 20-hour practice./i)).toBeInTheDocument();
  });
});

