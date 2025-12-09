import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/feature-flags", () => ({ ENABLE_PROTOTYPE_ADMIN: true }));

import SettingsPage from "./page";

const mockSettingsPayload = {
  sourceOfTruth: {
    domains: {
      docs: {
        priority: ["code", "api_spec", "docs"],
        hints: ["slack"],
      },
    },
  },
  gitMonitor: {
    defaultBranch: "main",
    projects: {
      project_atlas: [
        {
          repoId: "org/repo",
          branch: "main",
        },
      ],
    },
  },
  automation: {
    docUpdates: {
      docs: {
        mode: "suggest_only",
      },
    },
  },
};

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => mockSettingsPayload,
    } as Response);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the key settings cards after loading data", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Source of truth")).toBeInTheDocument();
    });
    expect(screen.getByText("Git monitoring")).toBeInTheDocument();
  });
});


