# Issue Provider Contract (`/api/issues`)

Phase 9 introduces a pluggable issue provider so the dashboard can treat Cerebros as the canonical source of DocIssues while retaining synthetic fixtures for demos.

---

## 1. Provider interface

Located in `src/lib/issues/providers/types.ts`:

```ts
export type IssueProviderName = "synthetic" | "cerebros";

export interface IssueProviderResult {
  projectId: string;
  provider: IssueProviderName;
  issues: DocIssue[];
  updatedAt: string;
}

export interface IssueProvider {
  name: IssueProviderName;
  fetchIssues(projectId: string): Promise<IssueProviderResult>;
}
```

Set `ISSUE_PROVIDER=synthetic|cerebros` (defaults to `synthetic`).

### Synthetic provider
- Reads `docIssues` from `lib/mock-data`.
- Automatically attaches `dashboardUrl` (`/projects/:id/issues/:issueId`) and `cerebrosUrl` (`https://cerebros.example.com/...`).

### Cerebros provider (stub)
- Requires `CEREBROS_API_BASE` (or `NEXT_PUBLIC_CEREBROS_API_BASE`).
- Calls `GET <CEREBROS_API_BASE>/api/doc-issues?projectId=:id`.
- Maps the payload to the dashboard’s `DocIssue` shape (falling back to sane defaults if fields are missing).
- If the request fails (network error, missing env, etc.) the route falls back to the synthetic provider.

---

## 2. `/api/issues` route

Usage:

```
GET /api/issues?projectId=project_atlas
```

Response:

```jsonc
{
  "projectId": "project_atlas",
  "provider": "cerebros",
  "issues": [
    {
      "id": "issue_atlas_001",
      "componentId": "comp:atlas-core",
      "severity": "high",
      "status": "triage",
      "dashboardUrl": "/projects/project_atlas/issues/issue_atlas_001",
      "cerebrosUrl": "https://cerebros.example.com/projects/project_atlas/issues/issue_atlas_001",
      // ... other DocIssue fields
    }
  ],
  "updatedAt": "2025-12-01T22:10:11.123Z",
  "fallback": false
}
```

If the configured provider fails, the response includes:

```json
{ "fallback": true, "fallbackProvider": "cerebros" }
```

---

## 3. Integration points

1. **`/api/activity`** now enriches each project with issues fetched via the provider so the dashboard’s hydration flow automatically receives the latest DocIssues.
2. **Client components** rely on the `dashboardUrl` / `cerebrosUrl` precomputed by the provider, so deep linking stays consistent regardless of the underlying source.

---

## 4. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `/api/issues` returns 500 when `ISSUE_PROVIDER=cerebros` | Ensure `CEREBROS_API_BASE` is set and reachable. The route logs `[issues] primary provider failed` before falling back. |
| Issues appear but deep links are missing | Verify `CEREBROS_APP_BASE` (or `NEXT_PUBLIC_CEREBROS_APP_BASE`) is set so the provider can build URLs. Defaults to `https://cerebros.example.com`. |
| Graph/context/tests show stale issues | Run `npm run test -- src/tests/api/backend.test.ts` to ensure all endpoints are in sync. |

---

## 5. Minimal setup checklist

1. `ISSUE_PROVIDER=cerebros`
2. `CEREBROS_API_BASE=https://cerebros.yourdomain.com`
3. (Optional) `CEREBROS_APP_BASE` for deep links
4. `npm run dev` → `/projects/:id` should now be populated with Cerebros-backed DocIssues.

