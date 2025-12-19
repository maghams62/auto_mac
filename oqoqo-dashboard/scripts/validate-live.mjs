#!/usr/bin/env node

/**
 * Simple helper to summarize live DocIssues from the running dashboard.
 *
 * Usage:
 *   npm run validate:live
 *   npm run validate:live -- --project project_atlas
 *   npm run validate:live -- --url http://localhost:4000/api/activity
 */

import process from "node:process";

const args = process.argv.slice(2);

function parseArgs(argv) {
  const options = {
    url: "http://localhost:3100/api/activity",
    project: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--url" && argv[i + 1]) {
      options.url = argv[i + 1];
      i += 1;
    } else if (arg === "--project" && argv[i + 1]) {
      options.project = argv[i + 1];
      i += 1;
    }
  }

  return options;
}

async function main() {
  const options = parseArgs(args);

  console.log(`Fetching live snapshot from ${options.url} ...`);
  let payload;
  try {
    const response = await fetch(options.url);
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    payload = await response.json();
  } catch (error) {
    console.error("Failed to fetch live snapshot:", error.message);
    process.exitCode = 1;
    return;
  }

  const projects = Array.isArray(payload?.projects) ? payload.projects : [];
  if (payload?.mode) {
    console.log(`Mode: ${payload.mode}`);
    if (payload.mode !== "atlas") {
      console.error("Expected /api/activity to return mode=atlas. Refusing to treat synthetic data as live.");
      process.exitCode = 1;
    }
  }
  if (!projects.length) {
    console.warn("No projects returned by /api/activity.");
    return;
  }

  const filteredProjects = options.project
    ? projects.filter((project) => project.id === options.project)
    : projects;

  if (!filteredProjects.length) {
    console.error(`Project '${options.project}' not found in live snapshot.`);
    process.exitCode = 1;
    return;
  }

  const summaries = filteredProjects.map((project) => {
    const liveIssues = (project.docIssues ?? []).filter((issue) =>
      issue.id?.startsWith("live_issue")
    );
    const issuesBySeverity = liveIssues.reduce(
      (acc, issue) => {
        acc[issue.severity] = (acc[issue.severity] ?? 0) + 1;
        return acc;
      },
      { critical: 0, high: 0, medium: 0, low: 0 }
    );

    return {
      projectId: project.id,
      projectName: project.name,
      liveIssues: liveIssues.length,
      critical: issuesBySeverity.critical ?? 0,
      high: issuesBySeverity.high ?? 0,
      medium: issuesBySeverity.medium ?? 0,
      low: issuesBySeverity.low ?? 0,
    };
  });

  console.table(summaries);

  const expanded = filteredProjects.flatMap((project) =>
    (project.docIssues ?? [])
      .filter((issue) => issue.id?.startsWith("live_issue"))
      .map((issue) => ({
        project: project.name,
        issueId: issue.id,
        component: issue.componentId,
        severity: issue.severity,
        sources: issue.divergenceSources?.join(", ") ?? "unknown",
        updatedAt: issue.updatedAt,
        summary: issue.summary,
      }))
  );

  if (expanded.length) {
    console.log("\nLive DocIssue details:");
    console.table(expanded);
  } else {
    console.log("\nNo live issues detected for the selected project(s).");
  }

  await validateDocIssues(activityProjectId(filteredProjects, options.project), options.url);
}

function activityProjectId(projects, explicit) {
  if (explicit) return explicit;
  return projects[0]?.id ?? null;
}

async function validateDocIssues(projectId, activityUrl) {
  if (!projectId) {
    console.warn("Skipping /api/doc-issues validation (project id unknown).");
    return;
  }
  const activityEndpoint = new URL(activityUrl);
  const base = `${activityEndpoint.protocol}//${activityEndpoint.host}`;
  const docIssuesUrl = `${base}/api/doc-issues?projectId=${encodeURIComponent(projectId)}`;
  console.log(`\nChecking doc issues at ${docIssuesUrl} ...`);

  try {
    const response = await fetch(docIssuesUrl);
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    const payload = await response.json();
    if (payload?.mode !== "atlas") {
      throw new Error(`Expected doc issue mode=atlas, received ${payload?.mode ?? "unknown"}`);
    }
    const issues = Array.isArray(payload?.issues) ? payload.issues : [];
    const placeholderLinks = issues
      .map((issue) => issue.githubUrl)
      .filter((url) => typeof url === "string" && url.includes("github.com/oqoqo/"));
    if (placeholderLinks.length) {
      throw new Error(`DocIssues still reference github.com/oqoqo: ${placeholderLinks.join(", ")}`);
    }
    console.log(`Doc issues OK (${issues.length} issues, live mode)`);
  } catch (error) {
    console.error("Doc issue validation failed:", error.message);
    process.exitCode = 1;
  }
}

main();

