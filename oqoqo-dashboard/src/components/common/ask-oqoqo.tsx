import { Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type AskContext = "project" | "component" | "issue";

interface AskOqoqoCardProps {
  context: AskContext;
  title: string;
  summary: string;
}

const promptTemplates: Record<AskContext, string[]> = {
  project: [
    "Summarize which components create the most drift right now.",
    "Which repos should I prioritize for documentation fixes this week?",
  ],
  component: [
    "Explain why drift score is trending on this component.",
    "List the docs or teams impacted if I ship changes today.",
  ],
  issue: [
    "Summarize the customer impact of this drift issue.",
    "What follow-up work should I hand to DX or support?",
  ],
};

export function AskOqoqoCard({ context, title, summary }: AskOqoqoCardProps) {
  const prompts = promptTemplates[context];

  return (
    <div className="rounded-3xl border border-dashed border-border/60 bg-muted/10 p-5">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="rounded-full border-primary/40 text-primary">
          <Sparkles className="mr-1 h-3.5 w-3.5" />
          Ask OQOQO
        </Badge>
        <span className="text-xs uppercase tracking-wide text-muted-foreground">LLM assist (stub)</span>
      </div>
      <div className="pt-3 text-sm text-muted-foreground">
        Future Cerebros agents will read this context and respond with prioritized next steps.
      </div>
      <div className="pt-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Context</div>
        <div className="text-sm font-semibold text-foreground">{title}</div>
        <p className="text-xs text-muted-foreground">{summary}</p>
      </div>
      <div className="pt-4 text-xs text-muted-foreground">
        Suggested prompts
        <ul className="list-disc space-y-1 pl-5 pt-2">
          {prompts.map((prompt) => (
            <li key={prompt}>{prompt}</li>
          ))}
        </ul>
      </div>
      <div className="pt-4">
        <Button variant="outline" className="rounded-full text-xs" disabled>
          Generate reasoning (coming soon)
        </Button>
      </div>
    </div>
  );
}

