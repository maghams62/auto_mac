## Live Git ingest status

- **Idempotent indexing** – Git commits/PRs/issues now use stable entity IDs (e.g., `commit:{sha}`, `pr:{repo}:{number}`) for both Qdrant points and Neo4j nodes, so rerunning `scripts/run_activity_ingestion.py` overwrites existing vectors/events instead of duplicating them.
- **Rich metadata** – Every Git chunk records `kind`, `repo_slug`, `project_id`, branch info, labels, component hits, and numeric identifiers, aligning with the Slack chunk schema for consistent filtering.
- **Comments + graph edges** – Optional review/issue comment ingestion (`activity_ingest.git.comments_enabled`) stores comments in Qdrant and as `GitEvent` nodes linked back to their parent PR/Issue via `DERIVED_FROM` relationships.
- **Repository awareness** – Git ingest now upserts `Repository` nodes, links them to matched components, and propagates `project_id` so cross-system impact queries can pivot by project/repo without querying GitHub.
- **Scheduler friendly** – `scripts/run_activity_ingestion.py` checks the config flags, logs when a source is disabled, and documents a cron example so ops can run Slack + Git ingest on a fixed interval.

