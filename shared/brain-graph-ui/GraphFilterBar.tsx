"use client";

import React, { useMemo } from "react";

type ModalityOption = {
  id: string;
  label: string;
  count: number;
  color: string;
};

type GraphFilterBarProps = {
  modalities: ModalityOption[];
  selectedModalities: string[] | null;
  onToggleModality: (id: string) => void;
  limit: number;
  onLimitChange: (value: number) => void;
  snapshotAt?: string;
  timeBounds?: { min: number; max: number };
  onSnapshotChange: (iso?: string) => void;
  isReplaying: boolean;
  onReplayToggle: () => void;
  showTimeControls: boolean;
};

export function GraphFilterBar({
  modalities,
  selectedModalities,
  onToggleModality,
  limit,
  onLimitChange,
  snapshotAt,
  timeBounds,
  onSnapshotChange,
  isReplaying,
  onReplayToggle,
  showTimeControls,
}: GraphFilterBarProps) {
  const allSelected = selectedModalities === null;

  const sliderValue = useMemo(() => {
    if (!timeBounds) return undefined;
    const fallback = timeBounds.max;
    if (!snapshotAt) return fallback;
    const parsed = Date.parse(snapshotAt);
    if (Number.isNaN(parsed)) {
      return fallback;
    }
    return Math.min(Math.max(parsed, timeBounds.min), timeBounds.max);
  }, [snapshotAt, timeBounds]);

  const formatSliderLabel = () => {
    if (!timeBounds || sliderValue === undefined) {
      return "Live";
    }
    return new Date(sliderValue).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  const LIMIT_MIN = 25;
  const LIMIT_MAX = 1200;
  const LIMIT_STEP = 25;

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-inner shadow-slate-900/40">
      <div className="flex flex-wrap gap-3">
        {modalities.length === 0 ? (
          <p className="text-sm text-slate-500">Modalities will appear once data loads.</p>
        ) : (
          modalities.map((modality) => {
            const isActive = allSelected || selectedModalities?.includes(modality.id);
            const normalizedId = modality.id.replace(/[^a-z0-9-]/gi, "-").toLowerCase();
            return (
              <button
                key={modality.id}
                type="button"
                onClick={() => onToggleModality(modality.id)}
                data-testid={`modality-chip-${normalizedId}`}
                aria-pressed={isActive}
                className={`flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition ${
                  isActive
                    ? "border-slate-200 bg-slate-200 text-slate-900"
                    : "border-slate-700 bg-slate-800/60 text-slate-200 hover:border-slate-500"
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: modality.color }} />
                {modality.label}
                <span className="text-xs text-slate-500">{modality.count}</span>
              </button>
            );
          })
        )}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col text-xs text-slate-400">
          Result limit ({limit})
          <input
            type="range"
            min={LIMIT_MIN}
            max={LIMIT_MAX}
            step={LIMIT_STEP}
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
            data-testid="result-limit-slider"
            className="w-48"
          />
        </label>

        {showTimeControls ? (
          <>
            {timeBounds ? (
              <div className="flex flex-col gap-1 text-xs text-slate-400">
                <span>Snapshot at ({formatSliderLabel()})</span>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    className="w-60"
                    min={timeBounds.min}
                    max={timeBounds.max}
                    step={Math.max(1, Math.round((timeBounds.max - timeBounds.min) / 40))}
                    value={sliderValue}
                    onChange={(event) => {
                      const next = Number(event.target.value);
                      onSnapshotChange(new Date(next).toISOString());
                    }}
                    data-testid="time-slider"
                  />
                  <button
                    type="button"
                    onClick={() => onSnapshotChange(undefined)}
                    className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-slate-500"
                  >
                    Live
                  </button>
                </div>
              </div>
            ) : null}

            {timeBounds ? (
              <button
                type="button"
                onClick={onReplayToggle}
                className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold ${
                  isReplaying ? "border-amber-400 text-amber-300" : "border-slate-600 text-slate-200 hover:border-slate-400"
                }`}
              >
                {isReplaying ? "Pause replay" : "Replay growth"}
              </button>
            ) : (
              <p className="text-[11px] text-slate-500">Timeline controls appear once events include timestamps.</p>
            )}
          </>
        ) : null}
      </div>
    </section>
  );
}


