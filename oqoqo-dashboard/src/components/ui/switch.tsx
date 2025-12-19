import * as React from "react";

import { cn } from "@/lib/utils";

export interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  onCheckedChange?: (checked: boolean) => void;
}

export const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, label, onCheckedChange, onChange, ...inputProps }, ref) => {
    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      onChange?.(event);
      onCheckedChange?.(event.target.checked);
    };

    const checked = inputProps.checked ?? false;

    return (
      <label className={cn("inline-flex items-center gap-2", label && "cursor-pointer")}>
        <span
          className={cn(
            "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer items-center rounded-full border border-border/80 bg-muted/60 transition-colors",
            checked ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
            className,
          )}
        >
          <input
            type="checkbox"
            className="sr-only"
            ref={ref}
            {...inputProps}
            onChange={handleChange}
          />
          <span
            className={cn(
              "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow transition",
              checked ? "translate-x-5" : "translate-x-1",
            )}
          />
        </span>
        {label ? <span className="text-sm text-muted-foreground">{label}</span> : null}
      </label>
    );
  },
);

Switch.displayName = "Switch";


