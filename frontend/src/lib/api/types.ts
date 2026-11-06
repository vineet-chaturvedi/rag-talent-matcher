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

export type EmployeeDetail = Schemas["EmployeeDetail"];
export type AvailabilityStatus = Schemas["AvailabilityStatus"];
export type EmployeeImportResult = Schemas["EmployeeImportResult"];
export type Resume = Schemas["ResumeOut"];
export type ResumeListItem = Schemas["ResumeListItem"];
export type BulkUploadResult = Schemas["BulkUploadResult"];
export type Profile = Schemas["ProfileOut"];
export type ProfileSkill = Schemas["ProfileSkillOut"];
export type ProfileJob = Schemas["ProfileJobOut"];
export type ProfileProject = Schemas["ProfileProjectOut"];

export type RoleStatus = Schemas["RoleStatus"];
export type Requirements = Schemas["Requirements"];
export type RequiredSkill = Schemas["RequiredSkill"];
export type MatchRun = Schemas["MatchRunOut"];
export type MatchRunStatus = Schemas["MatchRunStatus"];
export type MatchRunSummary = Schemas["MatchRunSummary"];
export type MatchResult = Schemas["MatchResultOut"];
export type JudgeVerdict = Schemas["JudgeVerdictOut"];
export type MustHaveVerdict = Schemas["MustHaveVerdictOut"];
export type SkillMatch = Schemas["SkillMatchOut"];
export type ScoreBreakdown = Schemas["ScoreBreakdown"];

export type Conversation = Schemas["ConversationOut"];
export type ConversationDetail = Schemas["ConversationDetail"];
export type AgentMessage = Schemas["MessageOut"];

export type MyFeedback = Schemas["MyFeedback"];
export type FeedbackRating = Schemas["FeedbackRating"];
export type FeedbackTarget = Schemas["FeedbackTarget"];
export type FeedbackItem = Schemas["FeedbackItem"];
export type FeedbackList = Schemas["FeedbackList"];
export type MatchFeedbackReason = NonNullable<Schemas["MatchFeedbackIn"]["reason"]>;
export type AgentFeedbackReason = NonNullable<Schemas["AgentFeedbackIn"]["reason"]>;
