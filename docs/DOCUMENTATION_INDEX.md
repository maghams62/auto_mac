# Documentation Index (Slimmed)

Only the references that help an LLM (or a new engineer) understand the current
Cerebros implementation are listed here. Historical write-ups live in
`docs/ARCHIVE_SUMMARY.md` and the git history.

---

## Core Guides

| Document | Path | Purpose |
|----------|------|---------|
| Project README | `README.md` | Workspace overview & setup |
| Critical Behavior | `CRITICAL_BEHAVIOR.md` | Runtime guardrails + expectations |
| Stable Codebase Guide | `docs/LLM_CODEBASE_GUIDE.md` | Canonical view of the current system |
| Implementation Status | `docs/IMPLEMENTATION_STATUS.md` | Snapshot of shipped features |
| Documentation Index | `docs/DOCUMENTATION_INDEX.md` | (This file) |

---

## Electron & Frontend

| Document | Path | Purpose |
|----------|------|---------|
| Electron UI Guide | `docs/development/ELECTRON_UI_GUIDE.md` | How to edit the Raycast-style UI safely |
| Launcher Startup Flow | `docs/architecture/launcher_startup_flow.md` | Lifecycle of the spotlight + expanded windows |
| Window Visibility State Machine | `docs/WINDOW_VISIBILITY_STATE_MACHINE.md` | Blur/focus logic for the launcher |
| Spotlight vs. Desktop Map | `docs/architecture/spotlight_vs_desktop.md` | Component/data flow comparison between launcher and expanded chat |
| Spotlight UX Audit | `docs/spotlight_ux_findings.md` | Current-state comparison vs. Raycast + improvement backlog |
| Stable Guide §3 | `docs/LLM_CODEBASE_GUIDE.md` | Launcher + desktop workflow details |
| Spotify Guardrails | `CRITICAL_BEHAVIOR.md` (section) | Constraints for media controls in spotlight view |

---

## Backend, Data & Integrations

| Document | Path | Purpose |
|----------|------|---------|
| Stable Guide §§4–5 | `docs/LLM_CODEBASE_GUIDE.md` | Backend entry points, data layout, runbooks |
| Synthetic Git Dataset | `docs/development/synthetic_git_dataset.md` | Git fixture structure for slash commands |
| Synthetic Slack Dataset | `docs/development/synthetic_slack_dataset.md` | Slack fixture structure |
| Vector Service Overview | `docs/operations/vector.md` | Qdrant / vector store wiring |
| Diagnostics: Electron Launcher | `docs/diagnostics/electron_launcher.md` | Troubleshooting Electron boot |

---

## Testing & Operations

| Document | Path | Purpose |
|----------|------|---------|
| Slash Command Smoke Tests | `docs/testing/SLASH_COMMANDS.md` | Manual + automated validation steps |
| Instant Startup Checklist | `docs/testing/INSTANT_STARTUP.md` | Verifies launcher behavior after builds |
| Stable Guide §6 | `docs/LLM_CODEBASE_GUIDE.md` | pytest focus + smoke scripts |
| Scripts & Checks | `tests/scripts/test_run_checks.py` | Programmatic health probe |

---

## Legacy Archive

- `docs/ARCHIVE_SUMMARY.md` – explains which historical documents/tests were
  removed and how to recover them from git history.
- Commit history keeps every deleted file if deeper context is required.

---

## Directory Map (Still Active)

| Directory | What to find |
|-----------|--------------|
| `docs/architecture/` | Launcher lifecycle and any diagrams we still rely on. |
| `docs/development/` | Implementation guides (Electron UI, synthetic datasets). |
| `docs/diagnostics/` | Runbooks for frontend/Electron/backend triage. |
| `docs/testing/` | Current manual/automated playbooks. |
| `prompts/` | Live prompt templates and few-shot examples. |

When adding new documentation, keep it short, link it from this index, and avoid
reintroducing feature-specific reports unless they describe functionality that
actively ships in the Raycast launcher + Slack/Git flows.
