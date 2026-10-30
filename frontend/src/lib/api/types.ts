import type { components } from "./schema";

/**
 * Friendly names for the generated API types, so code reads `Project` instead of
 * `components["schemas"]["ProjectOut"]`.
 *
 * Never write these shapes by hand: they come from FastAPI's Pydantic models via schema.d.ts
 * (`npm run api:types`). Add an alias here when a page needs a new one.
 */
type Schemas = components["schemas"];

export type User = Schemas["UserOut"];
export type UserRole = Schemas["UserRole"];
export type TokenResponse = Schemas["TokenResponse"];

export type Health = Schemas["HealthOut"];
export type Overview = Schemas["Overview"];
export type QueueStats = Schemas["QueueStats"];
export type ResumeStatus = Schemas["ResumeStatus"];

export type Project = Schemas["ProjectOut"];
export type ProjectRole = Schemas["RoleOut"];
export type ProjectStatus = Schemas["ProjectStatus"];
export type Employee = Schemas["EmployeeListItem"];
