// Adds DOM matchers to expect(): toBeInTheDocument(), toHaveAttribute(), toBeDisabled(), ...
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup()); // unmount what each test rendered, so tests don't affect each other
