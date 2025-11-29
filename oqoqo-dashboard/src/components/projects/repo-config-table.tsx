import { Copy } from "lucide-react";
import { RepoConfig } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface RepoConfigTableProps {
  repos: RepoConfig[];
}

export function RepoConfigTable({ repos }: RepoConfigTableProps) {
  const handleCopy = (repo: RepoConfig) => {
    navigator.clipboard.writeText(repo.repoUrl).catch(() => {});
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Repository</TableHead>
          <TableHead>Branch</TableHead>
          <TableHead>Service type</TableHead>
          <TableHead>Doc locations</TableHead>
          <TableHead>Labels</TableHead>
          <TableHead>Linked systems</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {repos.map((repo) => (
          <TableRow key={repo.id}>
            <TableCell>
              <div className="flex flex-col gap-1">
                <div className="font-semibold text-foreground">{repo.name}</div>
                <div className="text-xs text-muted-foreground">
                  {repo.repoUrl}
                  <Button variant="ghost" size="icon" className="ml-2 h-6 w-6" onClick={() => handleCopy(repo)}>
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </TableCell>
            <TableCell>
              <Badge variant="outline" className="rounded-full border-border/60">
                {repo.branch}
              </Badge>
            </TableCell>
            <TableCell>{repo.serviceType}</TableCell>
            <TableCell className="max-w-[200px] text-xs text-muted-foreground">
              {repo.docLocations.join(", ")}
            </TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {repo.labels.map((label) => (
                  <Badge key={label} variant="outline" className="rounded-full border-border/60">
                    {label}
                  </Badge>
                ))}
              </div>
            </TableCell>
            <TableCell>
              <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                {repo.linkedSystems.linearProject ? (
                  <span>Linear • {repo.linkedSystems.linearProject}</span>
                ) : null}
                {repo.linkedSystems.jiraProject ? (
                  <span>Jira • {repo.linkedSystems.jiraProject}</span>
                ) : null}
                {repo.linkedSystems.slackChannels?.length ? (
                  <span>Slack • {repo.linkedSystems.slackChannels.join(", ")}</span>
                ) : null}
                {repo.linkedSystems.supportTags?.length ? (
                  <span>Support • {repo.linkedSystems.supportTags.join(", ")}</span>
                ) : null}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

