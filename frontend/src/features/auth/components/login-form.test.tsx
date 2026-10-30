import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LoginState } from "../schemas";
import { LoginForm } from "./login-form";

/**
 * The form is tested with a FAKE Server Action (a plain async function). That is why LoginForm takes
 * `action` as a prop: no server, no network, and we can decide exactly what "the server" answers.
 */
describe("LoginForm", () => {
  it("sends the typed fields to the action", async () => {
    const action = vi.fn(async (...args: [LoginState, FormData]): Promise<LoginState> => (void args, {}));
    render(<LoginForm action={action} />);

    await userEvent.type(screen.getByLabelText("Email"), "admin@company.local");
    await userEvent.type(screen.getByLabelText("Password"), "secret-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(action).toHaveBeenCalledTimes(1);
    const formData = action.mock.calls[0]![1];
    expect(Object.fromEntries(formData)).toEqual({
      email: "admin@company.local",
      password: "secret-password",
    });
  });

  it("shows the server's message and keeps the email", async () => {
    const action = async (): Promise<LoginState> => ({ message: "Wrong email or password.", email: "a@b.co" });
    render(<LoginForm action={action} />);

    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
    expect(screen.getByLabelText("Email")).toHaveValue("a@b.co");
  });

  it("marks invalid fields for screen readers", async () => {
    const action = async (): Promise<LoginState> => ({
      fieldErrors: { email: ["That doesn't look like an email address."] },
    });
    render(<LoginForm action={action} />);

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const email = await screen.findByLabelText("Email");
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(email).toHaveAccessibleDescription("That doesn't look like an email address.");
  });

  it("shows the page's notice until the server answers", () => {
    render(<LoginForm action={async () => ({})} notice={<p role="status">Your session has ended.</p>} />);
    expect(screen.getByRole("status")).toHaveTextContent("Your session has ended");
  });
});
