import { NextResponse } from "next/server";

import { projects as mockProjects } from "@/lib/mock-data";

type DomainPolicy = {
  priority: string[];
  hints: string[];
};

type SettingsState = {
  sourceOfTruth: { domains: Record<string, DomainPolicy> };
  gitMonitor: {
    defaultBranch?: string;
    projects: Record<
      string,
      Array<{
        repoId: string;
        branch: string;
      }>
    >;
  };
  automation: { docUpdates: Record<string, { mode: string }> };
};

const defaultSettings: SettingsState = buildDefaultSettings();
let currentSettings: SettingsState = structuredClone(defaultSettings);

export async function GET() {
  return NextResponse.json({
    defaults: defaultSettings,
    effective: currentSettings,
  });
}

export async function PATCH(request: Request) {
  try {
    const patch = await request.json();
    currentSettings = mergeSettings(currentSettings, patch);
    return NextResponse.json({ ok: true });
  } catch (error) {
    console.warn("[settings] failed to parse patch payload", error);
    return NextResponse.json({ error: "Invalid settings payload" }, { status: 400 });
  }
}

function buildDefaultSettings(): SettingsState {
  const firstProject = mockProjects[0];
  const fallbackProjectId = firstProject?.id ?? "project_demo";
  const repoOverrides =
    firstProject?.repos.slice(0, 2).map((repo) => ({
      repoId: repo.id,
      branch: repo.branch || "main",
    })) ?? [];

  return {
    sourceOfTruth: {
      domains: {
        docs: { priority: ["code", "docs", "slack"], hints: ["slack"] },
        api_spec: { priority: ["api_spec", "code", "docs"], hints: ["tickets"] },
      },
    },
    gitMonitor: {
      defaultBranch: "main",
      projects: {
        [fallbackProjectId]: repoOverrides.length ? repoOverrides : [{ repoId: "org/repo", branch: "main" }],
      },
    },
    automation: {
      docUpdates: {
        docs: { mode: "suggest_only" },
        api_spec: { mode: "off" },
      },
    },
  };
}

function mergeSettings(base: any, patch: any): any {
  if (Array.isArray(base) && Array.isArray(patch)) {
    return patch;
  }
  if (isObject(base) && isObject(patch)) {
    const next: Record<string, unknown> = { ...base };
    Object.keys(patch).forEach((key) => {
      next[key] = key in base ? mergeSettings(base[key], patch[key]) : patch[key];
    });
    return next;
  }
  return patch ?? base;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}


