#!/usr/bin/env node

const defaultBase = process.env.SMOKE_BASE_URL ?? "http://localhost:3100";
const defaultProject = process.env.SMOKE_PROJECT_ID ?? "project_atlas";

function parseMode(value) {
  if (!value) return null;
  const normalized = value.toLowerCase();
  if (normalized === "synthetic") return "synthetic";
  if (normalized === "atlas" || normalized === "live") return "atlas";
  return null;
}

function parseCli() {
  const args = process.argv.slice(2);
  const options = {
    baseUrl: defaultBase,
    projectId: defaultProject,
    mode: null,
    allModes: false,
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--project" || arg === "-p") {
      options.projectId = args[++i] ?? options.projectId;
    } else if (arg === "--base" || arg === "-b") {
      options.baseUrl = args[++i] ?? options.baseUrl;
    } else if (arg === "--mode" || arg === "-m") {
      options.mode = parseMode(args[++i]) ?? options.mode;
    } else if (arg === "--synthetic" || arg === "-s") {
      options.mode = "synthetic";
    } else if (arg === "--all-modes" || arg === "--both") {
      options.allModes = true;
    }
  }
  return options;
}

function withMode(path, mode) {
  if (!mode) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}mode=${mode}`;
}

async function fetchJson(baseUrl, path, init) {
  const url = new URL(path, baseUrl);
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
    ...init,
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${url}`);
  }
  return response.json();
}

async function runScenario(baseUrl, projectId, mode) {
  const modeLabel = mode ?? "auto";
  console.log(`\n→ Running API smoke against ${baseUrl} (project=${projectId}, mode=${modeLabel})`);
  const activity = await fetchJson(baseUrl, withMode("/api/activity", mode));
  const activityMode = activity.mode ?? "unknown";
  const activityProject = activity.projects.find((project) => project.id === projectId);
  if (!activityProject) {
    throw new Error(`Project ${projectId} missing from /api/activity response`);
  }
  console.log(
    `✔ /api/activity → mode=${activity.mode} projects=${activity.projects.length} components=${activityProject.components.length}`
  );

  const graph = await fetchJson(baseUrl, withMode(`/api/graph-snapshot?projectId=${encodeURIComponent(projectId)}`, mode));
  const graphComponentIds = new Set((graph.snapshot?.components ?? []).map((component) => component.id));
  console.log(
    `✔ /api/graph-snapshot → provider=${graph.provider} components=${graph.snapshot?.componentCount ?? "?"} fallback=${Boolean(
      graph.fallback
    )}`
  );

  const metrics = await fetchJson(baseUrl, withMode("/api/graph-metrics", mode));
  const kpiCount = metrics.metrics?.kpis?.length ?? 0;
  console.log(
    `✔ /api/graph-metrics → provider=${metrics.provider} kpis=${kpiCount} fallback=${Boolean(metrics.fallback)}`
  );

  const issues = await fetchJson(baseUrl, withMode(`/api/issues?projectId=${encodeURIComponent(projectId)}`, mode));
  console.log(
    `✔ /api/issues → provider=${issues.provider} issues=${issues.issues?.length ?? 0} fallback=${Boolean(
      issues.fallback
    )}`
  );

  const contextTarget = issues.issues?.[0]?.id;
  if (contextTarget) {
    const context = await fetchJson(baseUrl, withMode("/api/context", mode), {
      method: "POST",
      body: JSON.stringify({ projectId, issueId: contextTarget }),
    });
    console.log(
      `✔ /api/context → snippets=${context.snippets?.length ?? 0} provider=${context.provider ?? "n/a"} fallback=${Boolean(
        context.fallback
      )}`
    );
  } else {
    console.log("⚠ /api/context skipped (no issues returned)");
  }

  const componentIdsFromActivity = new Set(activityProject.components.map((component) => component.id));
  const inconsistentIssues =
    issues.issues?.filter(
      (issue) =>
        !componentIdsFromActivity.has(issue.componentId) || !graphComponentIds.has(issue.componentId)
    ) ?? [];

  await assertImpactDocIssues(baseUrl, projectId, mode);

  const treatedSynthetic = (mode ?? "").toLowerCase() === "synthetic" || activityMode === "synthetic";
  if (inconsistentIssues.length) {
    console.warn(
      `⚠ Detected ${inconsistentIssues.length} issues referencing component IDs missing from activity/graph snapshots`
    );
    inconsistentIssues.slice(0, 5).forEach((issue) => {
      console.warn(`  - Issue ${issue.id} references ${issue.componentId}`);
    });
    if (treatedSynthetic) {
      console.warn("  ↪ Synthetic fixtures can drift; recording mismatch without failing.");
    } else {
      console.warn("  ↪ Live mode expects component parity; failing the smoke test.");
      process.exitCode = 1;
    }
  } else {
    console.log("✔ Component IDs align across activity, graph, and issues.");
  }
}

async function main() {
  const options = parseCli();
  const modesToRun = options.mode
    ? [options.mode]
    : options.allModes
    ? ["atlas", "synthetic"]
    : [null];
  console.log("Hint: override with --base/--project/--mode or use --both to run live+synthetic.\n");
  for (const mode of modesToRun) {
    await runScenario(options.baseUrl, options.projectId, mode);
  }
}

async function assertImpactDocIssues(baseUrl, projectId, mode) {
  const params = new URLSearchParams({ source: "impact-report" });
  if (projectId) {
    params.set("project_id", projectId);
  }

  const defaultResponse = await fetchJson(baseUrl, withMode(`/api/impact/doc-issues?${params.toString()}`, mode));
  ensureDocIssues(defaultResponse, "default impact response");
  console.log(
    `✔ /api/impact/doc-issues → mode=${defaultResponse.mode ?? "n/a"} fallback=${Boolean(
      defaultResponse.fallback
    )} alerts=${defaultResponse.doc_issues.length}`
  );

  const syntheticResponse = await fetchJson(
    baseUrl,
    `/api/impact/doc-issues?${params.toString()}&mode=synthetic`
  );
  ensureDocIssues(syntheticResponse, "synthetic impact response");
  if (!syntheticResponse.fallback) {
    console.warn("⚠ Expected synthetic fallback payload to set fallback=true");
  }
  console.log(
    `✔ /api/impact/doc-issues (synthetic) → fallback=${Boolean(
      syntheticResponse.fallback
    )} alerts=${syntheticResponse.doc_issues.length}`
  );
}

function ensureDocIssues(payload, label) {
  if (!payload || !Array.isArray(payload.doc_issues)) {
    throw new Error(`Impact doc-issues payload malformed for ${label}`);
  }
  const invalidEntries = payload.doc_issues.filter((issue) => typeof issue !== "object");
  if (invalidEntries.length) {
    throw new Error(`Impact doc-issues payload contained ${invalidEntries.length} invalid entries`);
  }
}

main().catch((error) => {
  console.error("Smoke test failed:", error);
  process.exitCode = 1;
});

