# Legacy Documentation & Test Archive

The repository previously contained dozens of point-in-time reports for
deprecated surfaces (email, WhatsApp, maps, older Spotify flows, etc.) plus
large regression logs and ad-hoc plans. Those files made it harder for LLMs to
reason about the current Cerebros focus (the Raycast-style launcher with Slack,
Git, and Spotify integrations), so they have been removed from the working tree.

This note captures where that historical context lived and how to recover it if
needed.

## What Was Trimmed

- **Patch / Fix Write-ups** – documents such as `FINAL_SPOTIFY_FIX.md`,
  `EMAIL_*_SUMMARY.md`, `SLASH_COMMAND_FIX_SUMMARY.md`, and other root-level
  reports now live only in git history. They primarily described temporary
  debugging efforts from pre-launch features.
- **Entire Legacy Doc Trees** – `docs/agents/`, `docs/features/`,
  `docs/architecture/*` (except `launcher_startup_flow.md`), and similar
  directories were removed so only the handful of guides referenced by
  `docs/DOCUMENTATION_INDEX.md` remain.
- **Changelog Directory** – everything in `docs/changelog/` was dropped in favor
  of the concise `docs/IMPLEMENTATION_STATUS.md` and the commit history.
- **Legacy Feature Plans** – guides for discontinued agents (WhatsApp, Twitter,
  Maps trip planner, etc.) were deleted to keep the docs focused on the current
  slash-command surface.
- **Obsolete Tests & Scripts** – regression runners, demo scripts, `tests/legacy/`,
  Playwright UI snapshots, JSON result dumps, and `scripts/testing/` were
  removed; see below for the minimal test suite that remains.

## How To Retrieve Details

All of the removed files remain available via git history. Use commands such as:

```bash
git log -- <path-to-removed-file>
git show <commit>:<path-to-removed-file>
```

If a specific document or test case becomes relevant again, restore it with
`git checkout <commit> -- <path>`, then add it back with the updated context.

## What To Read Instead

- `README.md` and `CRITICAL_BEHAVIOR.md` – current runtime expectations.
- `docs/LLM_CODEBASE_GUIDE.md` – primary orientation guide for coding LLMs.
- `docs/development/ELECTRON_UI_GUIDE.md` – Electron/Next.js workflow.
- `docs/architecture/launcher_startup_flow.md` – lifecycle of the Raycast view.
- `docs/development/synthetic_git_dataset.md` &
  `docs/development/synthetic_slack_dataset.md` – authoritative dataset info.
- `docs/testing/SLASH_COMMANDS.md` – how to validate the current slash stack.

Please keep new documentation concise and focused on active functionality so
future contributors (human or LLM) can ramp quickly.

