#!/usr/bin/env node

const defaultBase = process.env.SMOKE_BASE_URL ?? "http://localhost:3000";
const defaultProject = process.env.SMOKE_PROJECT_ID ?? "project_atlas";

function parseCli() {
  const args = process.argv.slice(2);
  const options = {
    baseUrl: defaultBase,
    projectId: defaultProject,
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--project" || arg === "-p") {
      options.projectId = args[++i] ?? options.projectId;
    } else if (arg === "--base" || arg === "-b") {
      options.baseUrl = args[++i] ?? options.baseUrl;
    }
  }
  return options;
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

async function main() {
  const options = parseCli();
  console.log(`Running API smoke against ${options.baseUrl} (project=${options.projectId})\n`);

  const activity = await fetchJson(options.baseUrl, "/api/activity");
  const activityProject = activity.projects.find((project) => project.id === options.projectId);
  if (!activityProject) {
    throw new Error(`Project ${options.projectId} missing from /api/activity response`);
  }
  console.log(
    `✔ /api/activity → mode=${activity.mode} projects=${activity.projects.length} components=${activityProject.components.length}`
  );

  const graph = await fetchJson(
    options.baseUrl,
    `/api/graph-snapshot?projectId=${encodeURIComponent(options.projectId)}`
  );
  const graphComponentIds = new Set(
    (graph.snapshot?.nodes ?? []).filter((node) => node.type === "component").map((node) => node.id)
  );
  console.log(
    `✔ /api/graph-snapshot → provider=${graph.provider} nodes=${graph.counts?.nodes ?? "?"} fallback=${Boolean(
      graph.fallback
    )}`
  );

  const issues = await fetchJson(
    options.baseUrl,
    `/api/issues?projectId=${encodeURIComponent(options.projectId)}`
  );
  console.log(
    `✔ /api/issues → provider=${issues.provider} issues=${issues.issues?.length ?? 0} fallback=${Boolean(
      issues.fallback
    )}`
  );

  const contextTarget = issues.issues?.[0]?.id;
  if (contextTarget) {
    const context = await fetchJson(options.baseUrl, "/api/context", {
      method: "POST",
      body: JSON.stringify({ projectId: options.projectId, issueId: contextTarget }),
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

  if (inconsistentIssues.length) {
    console.warn(
      `⚠ Detected ${inconsistentIssues.length} issues referencing component IDs missing from activity/graph snapshots`
    );
    inconsistentIssues.slice(0, 5).forEach((issue) => {
      console.warn(`  - Issue ${issue.id} references ${issue.componentId}`);
    });
    process.exitCode = 1;
  } else {
    console.log("✔ Component IDs align across activity, graph, and issues.");
  }
}

main().catch((error) => {
  console.error("Smoke test failed:", error);
  process.exitCode = 1;
});

