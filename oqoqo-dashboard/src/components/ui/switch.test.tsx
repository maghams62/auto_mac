import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Switch } from "./switch";

describe("Switch", () => {
  it("triggers onCheckedChange when toggled", () => {
    const handleChange = vi.fn();
    render(<Switch aria-label="demo switch" checked={false} onCheckedChange={handleChange} />);

    const checkbox = screen.getByLabelText("demo switch");
    fireEvent.click(checkbox);

    expect(handleChange).toHaveBeenCalledWith(true);
  });
});


