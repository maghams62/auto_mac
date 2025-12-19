"use client";

import { useEffect, useState } from "react";
import { Area, Bar, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";

import type { TimelineBucket } from "@/lib/hooks/use-activity-drift-view";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface ComponentTimelineProps {
  timeline: TimelineBucket[];
  cursor: number;
  onCursorChange?: (next: number) => void;
}

export function ComponentTimeline({ timeline, cursor, onCursorChange }: ComponentTimelineProps) {
  const [internalCursor, setInternalCursor] = useState(() => Math.max(0, timeline.length - 1));

  useEffect(() => {
    setInternalCursor(Math.max(0, timeline.length - 1));
  }, [timeline]);

  const activeIndex = onCursorChange ? cursor : internalCursor;
  const setCursor = (value: number) => {
    if (onCursorChange) {
      onCursorChange(value);
    } else {
      setInternalCursor(value);
    }
  };

  const current = timeline[activeIndex];

  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle>Drift replay</CardTitle>
        <CardDescription>Scrub through the last few weeks to see when Git, Slack, and doc signals spiked.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {timeline.length ? (
          <>
            <div className="rounded-2xl border border-border/60 bg-muted/10 p-4 text-sm" data-testid="timeline-summary">
              {current ? (
                <div className="flex flex-wrap gap-4">
                  <span className="font-semibold text-foreground">{current.date}</span>
                  <span className="text-muted-foreground">Git events: {current.gitCount}</span>
                  <span className="text-muted-foreground">Slack complaints: {current.slackCount}</span>
                  <span className="text-muted-foreground">Doc issues opened: {current.docOpened}</span>
                  {current.driftScore != null ? (
                    <span className="text-muted-foreground">Drift score: {current.driftScore.toFixed(1)}</span>
                  ) : null}
                </div>
              ) : (
                <span>No events recorded for the selected day.</span>
              )}
            </div>
            <div className="h-[320px] w-full">
              <ResponsiveContainer>
                <ComposedChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.35)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#94a3b8" />
                  <YAxis yAxisId="events" stroke="#94a3b8" />
                  <YAxis yAxisId="scores" orientation="right" stroke="#94a3b8" />
                  <RechartsTooltip />
                  <Bar yAxisId="events" dataKey="gitCount" stackId="events" fill="#22d3ee" name="Git" />
                  <Bar yAxisId="events" dataKey="slackCount" stackId="events" fill="#60a5fa" name="Slack complaints" />
                  <Bar yAxisId="events" dataKey="ticketCount" stackId="events" fill="#fb923c" name="Tickets" />
                  <Bar yAxisId="events" dataKey="docOpened" stackId="events" fill="#f87171" name="Doc issues opened" />
                  <Area yAxisId="scores" type="monotone" dataKey="driftScore" stroke="#f97316" fill="rgba(249,115,22,0.15)" name="Drift score" />
                  <Area
                    yAxisId="scores"
                    type="monotone"
                    dataKey="activityScore"
                    stroke="#34d399"
                    fill="rgba(52,211,153,0.15)"
                    name="Activity score"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-col gap-2">
              <input
                type="range"
                min={0}
                max={Math.max(0, timeline.length - 1)}
                value={activeIndex}
                onChange={(event) => setCursor(Number(event.target.value))}
                className="w-full"
                data-testid="timeline-slider"
              />
              <div className="flex justify-between text-xs text-muted-foreground" data-testid="timeline-range-labels">
                <span data-testid="timeline-start">{timeline[0]?.date}</span>
                <span data-testid="timeline-end">{timeline[timeline.length - 1]?.date}</span>
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-border/60 p-4 text-sm text-muted-foreground">
            Timeline data isn&apos;t available for this component yet.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

