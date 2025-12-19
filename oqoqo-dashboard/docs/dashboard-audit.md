# Dashboard Audit & UX Findings (Dec 4, 2025)

## Route → Sections Map

| Route / Entry Point | Key Sections & Cards | Rendering Components |
| --- | --- | --- |
| `/projects` | Cockpit hero, add/edit project dialogs, project health grid | `ProjectsPage`, `ProjectCard`, `ProjectForm` |
| `/projects/[projectId]` (Today) | Hero doc-health card w/ ModeBadge, live status summary, _ActivityGraphPanel_ (separate track), “Doc issues to fix now”, “Latest drift signals”, “Docs impact alerts”, issue detail sheet | `ProjectTodayPage`, `ActivityGraphPanel`, `ImpactAlertsPanel`, `IssueDetailSheet` |
| `/projects/[projectId]/components` | Mode-aware hero, search/sort/filter toolbar, at-risk toggle, component cards | `ComponentsPage`, `ComponentGrid` |
| `/projects/[projectId]/components/[componentId]` | Component hero, live drift issues, Cerebros activity stats, signal timeline, Git/Docs/Slack/Tickets/Support tabs, semantic context tab, divergence insights, linked docs/repos, dependency cards, doc issue list, recent investigations, Ask Oqoqo card | `ComponentDetailPage`, `RecentInvestigationsCard`, `AskOqoqoCard` |
| `/projects/[projectId]/issues` | Live drift inbox summary, filter bar, issue list, detail sheet | `ProjectIssuesPage`, `IssueFilters`, `IssueList`, `IssueDetailSheet` |
| `/projects/[projectId]/issues/[issueId]` | Issue hero + metadata, unified timeline, linked artifacts, semantic context accordion, Ask Oqoqo card | `IssueDetailPage`, `IssueDetailBody`, `AskOqoqoCard` |
| `/projects/[projectId]/impact` | Cross-system hero, dependency map, docs impact alerts, cross-repo impact table | `ImpactPage`, `DependencyMap`, `ImpactAlertsPanel` |
| `/projects/[projectId]/configuration` | Setup cards (workspace, Option 1, Option 2), debug accordion containing operators’ CTA, sources overview table, project metadata, repo matrix, linked systems, export card, live ingest inspector, dataset references & snapshot preview | `ProjectConfigurationPage`, `SetupWorkspaceCard`, `SetupOptionOneCard`, `SetupOptionTwoCard`, `RepoConfigTable` |
| `/projects/[projectId]/investigations` | Traceability hero w/ filters, investigations list with evidence/tool-run previews | `ProjectInvestigationsPage`, `InvestigationList` |
| `/settings` | Source-of-truth policy card, Git monitoring overrides, automation & safety modes, data sources summary | `SettingsPage` |
| `/projects/[projectId]/activity` | System map, component summary, doc issues list, timeline slider, CTA panel (Activity Graph owner) | `ProjectActivityPage`, `SystemMapGraph`, `ComponentTimeline` — _out of scope per Activity Graph track_ |
| `/projects/[projectId]/graph` | 3D graph, KPI row, component detail panel, analytics charts, trace dialog (Activity Graph owner) | `ProjectGraphPage` — _out of scope per Activity Graph track_ |

## Feature Wiring Matrix

| Feature / Card | Route | Data Source | Wiring | UX verdict |
| --- | --- | --- | --- | --- |
| Project cockpit grid & metrics | `/projects` | Zustand `projects` store populated via `/api/activity` fallback to `mock-data` | ⚠️ | Looks live but defaults to synthetic data unless ingest succeeds; doc health scores never explain provenance. |
| Add / edit project dialogs | `/projects` | Local state only; `addProject` / `updateProject` mutate client store | ❌ | Pretends to persist new projects even though nothing survives reloads, undermining trust. |
| Today hero + live status summary | `/projects/[id]` | Store `project` + `liveStatus` (`/api/activity`) | ✅ | Mode badge + status copy clearly indicate whether data is synthetic vs live. |
| “Doc issues to fix now” card | `/projects/[id]` | Local `project.docIssues` (live issues injected via `/api/activity` provider) | ⚠️ | Shows top 3 but silently empties when live issue provider fails; no indication that we fell back to synthetic. |
| “Latest drift signals” rail | `/projects/[id]` | Aggregated `component.sourceEvents` from live snapshot merge | ⚠️ | Works in synthetic mode but often empty in live mode because git/slack ingest rarely maps components, so users see a dashed box telling them to connect sources. |
| Impact alerts panel | `/projects/[id]` & `/impact` | `/api/impact/doc-issues` → Cerebros impact API, fallback to synthetic | ⚠️ | Fetch errors surface as a generic banner and the card returns empty even when doc issues exist; filters expose raw IDs that PMs don’t recognize. |
| Component grid + filters | `/projects/[id]/components` | Store `project.components` filtered client-side | ✅ | Sorting/filters respond instantly and respect live/synthetic mode; copy aligns with Option 1 story. |
| Component detail: live drift issues card | `/projects/[id]/components/[cid]` | `filterIssuesWithContext` over store docIssues | ✅ | Renders deterministic issues with severity badges; clear CTAs into issue detail. |
| Component detail: Cerebros activity stats | `/projects/[id]/components/[cid]` | Direct fetch to `NEXT_PUBLIC_CEREBROS_API_BASE` | ⚠️ | Hidden entirely unless env var is set; when configured it can still throw blocking errors that bubble up as red text. |
| Component detail: Semantic context tab | `/projects/[id]/components/[cid]` | `/api/context` (FastAPI context provider or synthetic fallback) | ⚠️ | Loading/error states exist, but non-technical viewers see raw snippets + “Source unavailable” copy; context toggle defaults closed, so value is hidden. |
| Component detail: Recent investigations | `/projects/[id]/components/[cid]` | `/api/investigations` (calls Cerebros Traceability) | ⚠️ | Shows errors inline but depends on backend; CTA to full investigations page often 404s when upstream returns HTML errors. |
| Issues page: live drift inbox + filters | `/projects/[id]/issues` | Store docIssues + `issueFilters` state | ✅ | Mode badge + description explain whether we’re in live, error, or synthetic; filters behave predictably. |
| Issue detail: unified timeline + semantic context | `/projects/[id]/issues/[issueId]` | Component events + `/api/context` | ⚠️ | Timeline invents “triaged” events from static data; context fetch failures show plain text errors, eroding confidence during demos. |
| Cross-system impact (dependency map + table) | `/projects/[id]/impact` | Static `project.dependencies` & doc issue counts | ⚠️ | Always synthetic; doesn’t reflect live mode even though page claims “Live snapshot”. Table columns expose internal IDs and contract names without explanation. |
| Configuration: Setup Workspace card | `/projects/[id]/configuration` | Store `project` + `liveSnapshot` timestamps | ✅ | Communicates wiring state clearly with badges + LiveRecency. |
| Configuration: Option 1 card (Activity summary) | `/projects/[id]/configuration` | Direct fetch to Cerebros `/api/activity/top-components` with synthetic fallback | ⚠️ | When backend is unreachable it silently shows fallback copy but still labels itself “Activity graph is live”, confusing PMs. |
| Configuration: Option 2 card (Doc issues) | `/projects/[id]/configuration` | `/api/doc-issues` (impact proxy) | ⚠️ | Makes another doc issue fetch even though Today + Issues already show the same data; duplicate numbers drift when backend partially fails. |
| Configuration: Dataset references & snapshot inspector | `/projects/[id]/configuration` | `project.datasetRefs`, `exportSnapshot` (synthetic JSON) | ✅ | Accurately reflects synthetic sources and provides honest “Snapshot unavailable” copy when missing. |
| Investigations list page | `/projects/[id]/investigations` | Server component calling `/api/investigations` without response guards | ⚠️ | Any upstream 502 (HTML body) crashes the route because `.json()` is called unconditionally; filters work only in synthetic mode. |
| Settings control surface | `/settings` | `/api/settings` (in-memory defaults) | ⚠️ | Entirely local mock; PATCH mutates server memory but nothing propagates to Cerebros, so buttons give false sense of control. |
| Ask Oqoqo cards | Several pages | No backend; static prompts with disabled button | ❌ | Labeled “LLM assist (stub)” with a disabled CTA, signaling unfinished work on every page. |

### Supporting code references

```
27:47:oqoqo-dashboard/src/app/(dashboard)/projects/page.tsx
const handleCreate = async (draft: ProjectDraft) => {
  await addProject(draft);
  setCreateOpen(false);
};

const handleEdit = async (draft: ProjectDraft) => {
  if (!draft.id) return;
  updateProject(draft.id, (project) => ({
    ...project,
    name: draft.name,
    description: draft.description,
    horizon: draft.horizon,
    tags: draft.tags,
    repos: draft.repos,
    pulse: {
      ...project.pulse,
      lastRefreshed: new Date().toISOString(),
    },
  }));
  setEditingProject(null);
};
```

```
52:79:oqoqo-dashboard/src/components/impact/impact-alerts-panel.tsx
useEffect(() => {
  const controller = new AbortController();
  const loadAlerts = async () => {
    setState("loading");
    try {
      const payload = await fetchJsonOrThrow<ImpactDocIssueResponse>(`/api/impact/doc-issues?${queryString}`, {
        signal: controller.signal,
        cache: "no-store",
      });
      const mapped = (payload?.doc_issues ?? []).map(mapDocIssueToAlert);
      if (!controller.signal.aborted) {
        setAlerts(mapped);
        setModeMeta({
          mode: payload.mode ?? "synthetic",
          fallback: Boolean(payload.fallback),
        });
        setState("ready");
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      console.error("[ImpactAlertsPanel] Failed to fetch doc issues", error);
      setState("error");
    }
  };
  loadAlerts();
  return () => controller.abort();
}, [queryString]);
```

```
27:61:oqoqo-dashboard/src/components/setup/option-one-card.tsx
useEffect(() => {
  let cancelled = false;

  const load = async () => {
    if (!isCerebrosApiConfigured()) {
      setRows(fallbackRows);
      setError(null);
      return;
    }

    setLoading(true);
    try {
      const data = await fetchTopComponents({ limit: 5 });
      if (!cancelled) {
        setRows(data);
        setError(null);
      }
    } catch (err) {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Failed to load activity graph data");
        setRows(fallbackRows);
      }
    } finally {
      if (!cancelled) {
        setLoading(false);
      }
    }
  };

  load();
  return () => {
    cancelled = true;
  };
}, [fallbackRows]);
```

```
32:92:oqoqo-dashboard/src/components/setup/option-two-card.tsx
useEffect(() => {
  let cancelled = false;

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", "3");
      params.set("projectId", project.id);
      const payload = await fetchJsonOrThrow<DocIssuesResponse>(`/api/doc-issues?${params.toString()}`, {
        cache: "no-store",
      });
      if (!cancelled) {
        setIssues(payload.issues ?? []);
        setMode(payload.mode ?? "synthetic");
      }
    } catch (err) {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Failed to load impact data");
        setIssues(project.docIssues.slice(0, 3));
      }
    } finally {
      if (!cancelled) {
        setLoading(false);
      }
    }
  };

  load();
  return () => {
    cancelled = true;
  };
}, [project]);
```

```
736:805:oqoqo-dashboard/src/app/(dashboard)/projects/[projectId]/components/[componentId]/page.tsx
useEffect(() => {
  let cancelled = false;
  const load = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        projectId,
        componentId,
        limit: String(RECENT_INVESTIGATION_LIMIT),
      });
      const response = await fetch(`/api/investigations?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }
      const payload = (await response.json()) as InvestigationResponse;
      if (!cancelled) {
        setInvestigations(payload.investigations ?? []);
        setError(null);
      }
    } catch (err) {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Failed to load investigations");
        setInvestigations([]);
      }
    } finally {
      if (!cancelled) {
        setLoading(false);
      }
    }
  };
  load();
  return () => {
    cancelled = true;
  };
}, [projectId, componentId]);
```

```
122:140:oqoqo-dashboard/src/app/(dashboard)/projects/[projectId]/issues/[issueId]/page.tsx
useEffect(() => {
  if (!projectId || !issue?.id) {
    return;
  }
  let cancelled = false;
  dispatchContext({ type: "LOADING" });
  requestContextSnippets({ projectId, issueId: issue.id })
    .then((response) => {
      if (!cancelled) {
        dispatchContext({ type: "SUCCESS", data: response });
      }
    })
    .catch((error) => {
      if (!cancelled) {
        dispatchContext({
          type: "ERROR",
          error: error instanceof Error ? error.message : "Failed to load context snippets",
        });
      }
    });
  return () => {
    cancelled = true;
  };
}, [projectId, issue?.id]);
```

```
52:107:oqoqo-dashboard/src/app/(dashboard)/projects/[projectId]/investigations/page.tsx
const response = await fetch(`${origin}/api/investigations?${query.toString()}`, {
  cache: "no-store",
});
const payload = (await response.json()) as InvestigationsResponse;

return (
  ...
  <ModeBadge mode={payload.mode} />
  ...
  <InvestigationList investigations={payload.investigations} />
);
```

```
33:60:oqoqo-dashboard/src/components/common/ask-oqoqo.tsx
return (
  <div className="rounded-3xl border border-dashed border-border/60 bg-muted/10 p-5">
    <div className="flex items-center gap-2">
      <Badge variant="outline" className="rounded-full border-primary/40 text-primary">
        <Sparkles className="mr-1 h-3.5 w-3.5" />
        Ask Oqoqo
      </Badge>
      <span className="text-xs uppercase tracking-wide text-muted-foreground">LLM assist (stub)</span>
    </div>
    ...
    <Button variant="outline" className="rounded-full text-xs" disabled>
      Generate reasoning (coming soon)
    </Button>
  </div>
);
```

## Non-Functional / Placeholder / Broken Elements (Prioritized)

1. **Project creation/editing (`/projects`)** – dialogs only mutate client memory (`addProject`, `updateProject`) so new projects disappear on refresh. _Action: Hide for demo or gate behind “Prototype admin” until persistence exists._
2. **Ask Oqoqo cards (component & issue detail pages)** – explicitly marked “LLM assist (stub)” with disabled CTA, so every surface reminds viewers of missing functionality. _Action: Replace with a small “Coming soon” badge or hide entirely._
3. **Project Investigations page** – calls `/api/investigations` without checking `response.ok`; HTML error bodies throw inside `response.json()` and crash the route. _Action: Fix wiring now by guarding response status + surfacing clear fallback copy._
4. **Configuration Option 1 card** – fetches Cerebros activity directly from the browser; without `NEXT_PUBLIC_CEREBROS_API_BASE` it silently drops to synthetic while still claiming “Activity graph is live”. _Action: Either proxy via Next API (with status metadata) or hide when live ingest is unavailable._
5. **Configuration Option 2 card** – duplicates doc issue data already shown elsewhere and exposes upstream errors verbatim (raw fetch exception strings). _Action: Merge with Today/Impact signals or hide for demo until it adds unique insights._
6. **Settings surface** – `/api/settings` is an in-memory mock; saving changes does nothing beyond current process. _Action: Label as “Prototype control surface” or disable until connected to real backend._
7. **Impact dependency map/table** – data is 100% synthetic (`project.dependencies`) and never reflects live mode even though page copy promises “Live snapshot”. _Action: Either annotate with “Synthetic example” or hide until dependencies can be ingested._

## Narrative Critique

### PM / Non-technical POV
The dashboard currently reads like a collection of interesting panels rather than a cohesive story. Option 1 (doc risk) and Option 2 (cross-system impact) both show up on the Today page, configuration cards, and impact page, but they repeat the same stats instead of walking me from “overall health → top fires → what to fix next.” Noise comes from raw IDs, repo codes, and duplicate doc issue numbers across Today, Impact, and Configuration. The Ask Oqoqo stubs and broken add-project dialog make it feel prototype-grade. I’d keep the Today hero, top issues list, and ModeBadge because they clearly communicate state; I’d hide Option 1/2 setup cards, Ask Oqoqo, and most of the configuration tables for a non-technical demo until they’re wired.

### Engineer POV
Engineers can find useful detail (component grids, issue filters, dependency map), but each surface relies on slightly different data plumbing. Investigations, context snippets, and Cerebros activity cards all hit different APIs with inconsistent error handling, so dependency failures bubble up as blank cards or crashes. Mode awareness is inconsistent: some panels (hero, issues) respect `modePreference`, while others (dependency map, configuration cards) stay synthetic regardless. The doc issue data is repeated in three places with different filters, which increases cognitive load without adding insight. Consolidating doc issue telemetry into a single inbox + component view, and ensuring every card reports its data source/status, would restore trust. Until then, engineers will question whether the “live” numbers actually came from live ingest.

## Redesign Plan (Aligning Option 1 & Option 2)

1. **Core narrative**
   - Treat the Today page + Issues/Components surfaces as the Option 1 “documentation drift → fix it now” flow.
   - Reserve the Impact page + investigations for the Option 2 “cross-system blast radius” story.
   - Introduce a single “Data source” pill (ModeBadge + fallback label) for every retained card; hide or badge anything that is synthetic-only.

2. **Today page (Option 1 focus)**
   - Keep hero + live status and rename supporting copy to “Option 1: documentation health”.
   - Merge “Doc issues to fix now” and “Impact alerts” into one column so PMs see a single prioritized list.
   - Keep Latest Signals as a horizontal rail but add a small caption clarifying when it’s empty because we’re in synthetic mode.
   - Remove Ask Oqoqo stubs; instead, surface a single “Ask Cerebros in Slack” button that deep-links to the existing command.

3. **Components & Issues**
   - Keep component grid + filters but add inline filters for Option 1 metrics (drift/activity). When no live data, show a “Synthetic demo” pill.
   - Simplify Issue detail: collapse semantic context + Ask Oqoqo into one “Context & evidence” accordion with honest empty states.
   - Ensure issue modals/pages reuse the same doc issue data source so counts stay in sync with Today.

4. **Impact page (Option 2 focus)**
   - Lead with a short paragraph tying dependencies + doc issues to Option 2 goals (“understand upstream API blasts before automation”).
   - Keep dependency map + cross-repo table but add explicit “Synthetic dataset” badge unless live edges exist.
   - Keep Impact Alerts but rename copy to “Docs exposed by upstream changes” to differentiate from Option 1 inbox.

5. **Configuration & Settings**
   - Hide Add Project, Option 1, Option 2 setup cards, and Settings control surface behind `NEXT_PUBLIC_ENABLE_PROTOTYPE_ADMIN`.
   - Rebrand the remaining configuration content as “Data sources & setup” with one compact card summarizing Git/Slack wiring plus the dataset references table (for operators only).

6. **Traceability (Investigations & context)**
   - Move the investigations list link into the Impact page (since Option 2 users need it) and guard server fetches with response checks + fallback empty states.
   - When context APIs fail, downgrade cards to a bordered warning with actionable text (“Connect Cerebros context to see Slack/docs excerpts”).

7. **Mode toggle + wiring**
   - Treat the header ModeToggle as the source of truth. All client fetches (doc issues, investigations, context, option cards) must append `mode=<preference>` so toggling synthetic vs live actually changes payloads.
   - Expose the current mode/fallback per card via `ModeBadge` or a `Synthetic demo` chip to reduce confusion for PM demos.

