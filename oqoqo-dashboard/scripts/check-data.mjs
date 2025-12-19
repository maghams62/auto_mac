#!/usr/bin/env node

/**
 * Phase 0 helper: verify required env vars exist and synthetic dataset URLs are reachable.
 *
 * Usage:
 *   npm run check:data
 *   npm run check:data -- --project project_atlas
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import dotenv from "dotenv";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const appRootPath = resolve(scriptDir, "..");
const workspaceRootPath = resolve(appRootPath, "..");
const dataSourcesPath = resolve(scriptDir, "data-sources.json");
const dataSources = JSON.parse(readFileSync(dataSourcesPath, "utf-8"));

const REQUIRED_ENV_VARS = ["GITHUB_TOKEN", "GITHUB_ORG", "SLACK_TOKEN"];

function loadEnv() {
  const result = dotenv.config({ path: resolve(workspaceRootPath, ".env") });
  if (result.error) {
    console.warn("⚠️  Could not load .env file automatically. Continuing with process env.");
  }
}

function checkEnvVars() {
  console.log("🔍 Checking required environment variables...");
  const rows = REQUIRED_ENV_VARS.map((key) => ({
    variable: key,
    present: Boolean(process.env[key]),
  }));
  console.table(rows);

  const missing = rows.filter((row) => !row.present);
  if (missing.length) {
    console.warn("⚠️  Missing variables detected. Update your .env before running live validation.");
  } else {
    console.log("✅ All required env vars are present.");
  }
}

function parseArgs(argv) {
  const options = {
    project: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--project" && argv[i + 1]) {
      options.project = argv[i + 1];
      i += 1;
    }
  }

  return options;
}

async function checkDatasets(projectFilter) {
  console.log("\n📦 Verifying synthetic dataset sources...");
  const entries = Object.entries(dataSources.projects).filter(([projectId]) =>
    projectFilter ? projectId === projectFilter : true
  );

  if (!entries.length) {
    console.error(
      projectFilter
        ? `Project '${projectFilter}' not found in scripts/data-sources.json`
        : "No projects defined in scripts/data-sources.json"
    );
    process.exitCode = 1;
    return;
  }

  const results = [];

  for (const [projectId, sources] of entries) {
    for (const [source, url] of Object.entries(sources)) {
      if (!url) continue;
      try {
        const response = await fetch(url, { method: "HEAD" });
        results.push({
          project: projectId,
          source,
          status: response.ok ? "ok" : `HTTP ${response.status}`,
          url,
        });
      } catch (error) {
        results.push({
          project: projectId,
          source,
          status: `error: ${error.message}`,
          url,
        });
      }
    }
  }

  console.table(results.map(({ project, source, status }) => ({ project, source, status })));

  const failing = results.filter((row) => row.status !== "ok");
  if (failing.length) {
    console.warn("⚠️  Some dataset URLs are unreachable. Verify the repositories/branches or update data-sources.json.");
  } else {
    console.log("✅ All dataset URLs responded successfully.");
  }
}

async function main() {
  loadEnv();
  checkEnvVars();
  const options = parseArgs(process.argv.slice(2));
  await checkDatasets(options.project);
}

main().catch((error) => {
  console.error("Unexpected error while running check-data:", error);
  process.exitCode = 1;
});

