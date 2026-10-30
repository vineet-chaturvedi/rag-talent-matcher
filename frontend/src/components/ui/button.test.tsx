import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("is a real <button> by default", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" }).tagName).toBe("BUTTON");
  });

  it("asChild puts the button styles on the child (a link stays a link)", () => {
    render(
      <Button asChild variant="outline">
        <a href="https://example.com/help">Open help</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Open help" });
    expect(link).toHaveAttribute("href", "https://example.com/help");
    expect(link.className).toContain("border-input");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("lets a className override a default class (tailwind-merge)", () => {
    render(<Button className="h-12">Tall</Button>);
    const button = screen.getByRole("button", { name: "Tall" });
    expect(button.className).toContain("h-12");
    expect(button.className).not.toContain("h-9");
  });
});
