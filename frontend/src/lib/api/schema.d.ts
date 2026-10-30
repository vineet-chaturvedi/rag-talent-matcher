/**
 * GENERATED FILE: do not edit by hand.
 * Source: http://127.0.0.1:8010/openapi.json
 * Regenerate with: npm run api:types
 */

export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/change-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Change Password */
        post: operations["change_password_api_auth_change_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Users */
        get: operations["list_users_api_users_get"];
        put?: never;
        /** Create User */
        post: operations["create_user_api_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update User */
        patch: operations["update_user_api_users__user_id__patch"];
        trace?: never;
    };
    "/api/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Overview */
        get: operations["overview_api_overview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/employees/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Employees */
        post: operations["import_employees_api_employees_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/employees": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Employees */
        get: operations["list_employees_api_employees_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/employees/{employee_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Employee */
        get: operations["get_employee_api_employees__employee_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/employees/{employee_id}/resumes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Resume */
        post: operations["upload_resume_api_employees__employee_id__resumes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Bulk Upload */
        post: operations["bulk_upload_api_resumes_bulk_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Resumes */
        get: operations["list_resumes_api_resumes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/stats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Queue Stats */
        get: operations["queue_stats_api_resumes_stats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/reextract": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reextract All */
        post: operations["reextract_all_api_resumes_reextract_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/reembed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reembed All */
        post: operations["reembed_all_api_resumes_reembed_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/{resume_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Resume */
        get: operations["get_resume_api_resumes__resume_id__get"];
        put?: never;
        post?: never;
        /** Remove */
        delete: operations["remove_api_resumes__resume_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/{resume_id}/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Profile */
        get: operations["get_profile_api_resumes__resume_id__profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/{resume_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry */
        post: operations["retry_api_resumes__resume_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/search/semantic": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Search Semantic */
        post: operations["search_semantic_api_search_semantic_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/{resume_id}/chunks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resume Chunks */
        get: operations["resume_chunks_api_resumes__resume_id__chunks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Projects */
        get: operations["list_projects_api_projects_get"];
        put?: never;
        /** Create Project */
        post: operations["create_project_api_projects_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/projects/{project_id}/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Role */
        post: operations["create_role_api_projects__project_id__roles_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/roles/{role_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Role */
        get: operations["get_role_api_roles__role_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/roles/{role_id}/requirements/parse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Parse Requirements
         * @description Takes ~30-60 s on a CPU: the LLM reads the role description once; the result is stored.
         */
        post: operations["parse_requirements_api_roles__role_id__requirements_parse_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/roles/{role_id}/requirements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Update Requirements
         * @description A resource manager corrects what the AI parsed (e.g. moves a skill from must-have to nice-to-have).
         */
        put: operations["update_requirements_api_roles__role_id__requirements_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/roles/{role_id}/candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Find Candidates */
        post: operations["find_candidates_api_roles__role_id__candidates_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/roles/{role_id}/match": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Match */
        post: operations["start_match_api_roles__role_id__match_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/match-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Match Run */
        get: operations["get_match_run_api_match_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/roles/{role_id}/match-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Match Runs */
        get: operations["list_match_runs_api_roles__role_id__match_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/conversations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Conversations */
        get: operations["list_conversations_api_agent_conversations_get"];
        put?: never;
        /** Create Conversation */
        post: operations["create_conversation_api_agent_conversations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/conversations/{conversation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Conversation */
        get: operations["get_conversation_api_agent_conversations__conversation_id__get"];
        put?: never;
        post?: never;
        /** Delete Conversation */
        delete: operations["delete_conversation_api_agent_conversations__conversation_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/conversations/{conversation_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ask */
        post: operations["ask_api_agent_conversations__conversation_id__messages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/dev/chat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Dev Chat */
        post: operations["dev_chat_api_dev_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/dev/similarity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Dev Similarity */
        post: operations["dev_similarity_api_dev_similarity_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/dev/extract/{resume_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Dev Extract
         * @description Run LLM extraction on one resume and show everything - WITHOUT saving it. For experimenting.
         */
        post: operations["dev_extract_api_dev_extract__resume_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Root */
        get: operations["root__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AskRequest */
        AskRequest: {
            /**
             * Content
             * @example Who could lead a Kubernetes migration on AWS starting 1 December?
             */
            content: string;
            /**
             * Stream
             * @description true = Server-Sent Events while the agent works; false = one JSON reply
             * @default true
             */
            stream: boolean;
        };
        /** AskResponse */
        AskResponse: {
            /** Answer */
            answer: string;
            /** Events */
            events: {
                [key: string]: unknown;
            }[];
        };
        /** AvailabilityOut */
        AvailabilityOut: {
            status: components["schemas"]["AvailabilityStatus"];
            /** Allocation Percent */
            allocation_percent: number;
            /** Free Percent */
            free_percent: number;
            /** Available From */
            available_from: string | null;
            /** Fits */
            fits: boolean;
            /** Note */
            note: string;
        };
        /**
         * AvailabilityStatus
         * @enum {string}
         */
        AvailabilityStatus: "available" | "partial" | "allocated" | "on_leave";
        /** Body_bulk_upload_api_resumes_bulk_post */
        Body_bulk_upload_api_resumes_bulk_post: {
            /**
             * Files
             * @description Many PDF/DOCX files named like EMP-1001_anything.pdf
             */
            files: string[];
        };
        /** Body_import_employees_api_employees_import_post */
        Body_import_employees_api_employees_import_post: {
            /**
             * File
             * @description HR export as CSV (UTF-8). Required columns: employee_code, full_name
             */
            file: string;
        };
        /** Body_upload_resume_api_employees__employee_id__resumes_post */
        Body_upload_resume_api_employees__employee_id__resumes_post: {
            /**
             * File
             * @description PDF or DOCX
             */
            file: string;
        };
        /** BulkUploadResult */
        BulkUploadResult: {
            /** Uploaded */
            uploaded: number;
            /** Failed */
            failed: number;
            /** Items */
            items: components["schemas"]["UploadItemResult"][];
        };
        /** CandidateOut */
        CandidateOut: {
            /** Rank */
            rank: number;
            /** Employee Id */
            employee_id: number;
            /** Employee Code */
            employee_code: string;
            /** Full Name */
            full_name: string;
            /** Designation */
            designation: string | null;
            /** Location */
            location: string | null;
            /** Fused Score */
            fused_score: number;
            /** Ranks */
            ranks: {
                [key: string]: number | null;
            };
            /** Skill Score */
            skill_score: number;
            /** Must Matched */
            must_matched: components["schemas"]["SkillMatchOut"][];
            /** Must Missing */
            must_missing: string[];
            /** Nice Matched */
            nice_matched: components["schemas"]["SkillMatchOut"][];
            /** Keyword Snippets */
            keyword_snippets: string[];
            /** Vector Chunks */
            vector_chunks: components["schemas"]["ChunkEvidence"][];
            availability: components["schemas"]["AvailabilityOut"];
        };
        /** CandidatesRequest */
        CandidatesRequest: {
            /**
             * Top K
             * @default 15
             */
            top_k: number;
            /**
             * Only Available
             * @description Exclude people who can't take the role's allocation by its start date
             * @default false
             */
            only_available: boolean;
            /**
             * Signals
             * @default [
             *       "skills",
             *       "keyword",
             *       "vector"
             *     ]
             */
            signals: ("skills" | "keyword" | "vector")[];
        };
        /** CandidatesResponse */
        CandidatesResponse: {
            /** Role Id */
            role_id: number;
            /** Role Title */
            role_title: string;
            requirements: components["schemas"]["Requirements"];
            /** Candidates */
            candidates: components["schemas"]["CandidateOut"][];
            /** Timings */
            timings: {
                [key: string]: unknown;
            };
        };
        /** ChatRequest */
        ChatRequest: {
            /**
             * Prompt
             * @example In one sentence, what does a DevOps engineer do?
             */
            prompt: string;
            /**
             * Model
             * @default fast
             * @enum {string}
             */
            model: "fast" | "quality";
            /**
             * Temperature
             * @default 0
             */
            temperature: number;
            /**
             * System
             * @example You are a concise technical recruiter.
             */
            system?: string | null;
        };
        /** ChatResponse */
        ChatResponse: {
            /** Model */
            model: string;
            /** Answer */
            answer: string;
            /** Prompt Tokens */
            prompt_tokens: number;
            /** Output Tokens */
            output_tokens: number;
            /** Load Seconds */
            load_seconds: number;
            /** Prompt Tokens Per Second */
            prompt_tokens_per_second: number;
            /** Output Tokens Per Second */
            output_tokens_per_second: number;
        };
        /** ChunkEvidence */
        ChunkEvidence: {
            /** Section */
            section: string;
            /** Similarity */
            similarity: number;
            /** Text */
            text: string;
        };
        /** ConversationCreate */
        ConversationCreate: {
            /** Title */
            title?: string | null;
        };
        /** ConversationDetail */
        ConversationDetail: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Messages */
            messages: components["schemas"]["MessageOut"][];
        };
        /** ConversationOut */
        ConversationOut: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** DatabaseHealth */
        DatabaseHealth: {
            /** Reachable */
            reachable: boolean;
            /** Error */
            error?: string | null;
        };
        /** EmployeeCounts */
        EmployeeCounts: {
            /** Total */
            total: number;
            /** Active */
            active: number;
        };
        /** EmployeeDetail */
        EmployeeDetail: {
            /** Id */
            id: number;
            /** Employee Code */
            employee_code: string;
            /** Full Name */
            full_name: string;
            /** Email */
            email: string | null;
            /** Department */
            department: string | null;
            /** Designation */
            designation: string | null;
            /** Location */
            location: string | null;
            availability_status: components["schemas"]["AvailabilityStatus"];
            /** Allocation Percent */
            allocation_percent: number;
            /** Available From */
            available_from: string | null;
            /** Current Project Name */
            current_project_name: string | null;
            /** Is Active */
            is_active: boolean;
            /** Date Joined */
            date_joined: string | null;
            /** Manager Name */
            manager_name: string | null;
            /** Resumes */
            resumes: components["schemas"]["ResumeOut"][];
        };
        /** EmployeeImportResult */
        EmployeeImportResult: {
            /** Created */
            created: number;
            /** Updated */
            updated: number;
            /** Failed */
            failed: number;
            /** Errors */
            errors: components["schemas"]["RowError"][];
        };
        /** EmployeeListItem */
        EmployeeListItem: {
            /** Id */
            id: number;
            /** Employee Code */
            employee_code: string;
            /** Full Name */
            full_name: string;
            /** Email */
            email: string | null;
            /** Department */
            department: string | null;
            /** Designation */
            designation: string | null;
            /** Location */
            location: string | null;
            availability_status: components["schemas"]["AvailabilityStatus"];
            /** Allocation Percent */
            allocation_percent: number;
            /** Available From */
            available_from: string | null;
            /** Current Project Name */
            current_project_name: string | null;
            /** Is Active */
            is_active: boolean;
            current_resume?: components["schemas"]["ResumeOut"] | null;
        };
        /** EmployeeResult */
        EmployeeResult: {
            /** Rank */
            rank: number;
            /** Employee Id */
            employee_id: number;
            /** Employee Code */
            employee_code: string;
            /** Full Name */
            full_name: string;
            /** Designation */
            designation: string | null;
            /** Location */
            location: string | null;
            availability_status: components["schemas"]["AvailabilityStatus"];
            /** Allocation Percent */
            allocation_percent: number;
            /** Score */
            score: number;
            /** Matched Chunks */
            matched_chunks: components["schemas"]["MatchedChunk"][];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthOut */
        HealthOut: {
            /** App */
            app: string;
            /** Environment */
            environment: string;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "degraded" | "error";
            database: components["schemas"]["DatabaseHealth"];
            ollama: components["schemas"]["OllamaHealth"];
        };
        /** LoginRequest */
        LoginRequest: {
            /**
             * Email
             * @example admin@company.local
             */
            email: string;
            /** Password */
            password: string;
        };
        /** MatchRequest */
        MatchRequest: {
            /**
             * Top K
             * @description How many candidates to keep and score
             * @default 10
             */
            top_k: number;
            /**
             * Judge Top N
             * @description How many of them the LLM judge reads (0 = no judge)
             * @default 5
             */
            judge_top_n: number;
            /**
             * Only Available
             * @description Only people who can take the role's allocation by its start date
             * @default false
             */
            only_available: boolean;
        };
        /** MatchResultOut */
        MatchResultOut: {
            /** Rank */
            rank: number;
            /** Employee Id */
            employee_id: number;
            /** Employee Code */
            employee_code: string;
            /** Full Name */
            full_name: string;
            /** Designation */
            designation: string | null;
            /** Location */
            location: string | null;
            /** Final Score */
            final_score: number;
            /** Score Breakdown */
            score_breakdown: {
                [key: string]: unknown;
            };
            /** Explanation */
            explanation: {
                [key: string]: unknown;
            } | null;
        };
        /** MatchRunCounts */
        MatchRunCounts: {
            /** Total */
            total: number;
            /** By Status */
            by_status: {
                [key: string]: number;
            };
        };
        /** MatchRunOut */
        MatchRunOut: {
            /** Id */
            id: number;
            /** Role Id */
            role_id: number;
            /** Role Title */
            role_title: string;
            status: components["schemas"]["MatchRunStatus"];
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /** Finished At */
            finished_at: string | null;
            /** Error Message */
            error_message: string | null;
            /** Judged */
            judged: number;
            /** To Judge */
            to_judge: number;
            /** Settings */
            settings: {
                [key: string]: unknown;
            } | null;
            /** Results */
            results: components["schemas"]["MatchResultOut"][];
        };
        /**
         * MatchRunStatus
         * @enum {string}
         */
        MatchRunStatus: "running" | "completed" | "failed";
        /** MatchRunSummary */
        MatchRunSummary: {
            /** Id */
            id: number;
            status: components["schemas"]["MatchRunStatus"];
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /** Finished At */
            finished_at: string | null;
            /** Top */
            top: string[];
        };
        /** MatchedChunk */
        MatchedChunk: {
            /** Section */
            section: string;
            /** Similarity */
            similarity: number;
            /** Text */
            text: string;
        };
        /** MessageOut */
        MessageOut: {
            /** Id */
            id: number;
            /** Role */
            role: string;
            /** Content */
            content: string;
            /** Tool Calls */
            tool_calls: unknown[] | null;
            /** Tool Name */
            tool_name: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** ModelHealth */
        ModelHealth: {
            /** Name */
            name: string;
            /** Installed */
            installed: boolean;
        };
        /** OllamaHealth */
        OllamaHealth: {
            /** Reachable */
            reachable: boolean;
            /** Version */
            version?: string | null;
            /** Models */
            models?: {
                [key: string]: components["schemas"]["ModelHealth"];
            } | null;
            /** Error */
            error?: string | null;
        };
        /**
         * Overview
         * @description Everything the dashboard's number tiles need, in one small response (counts, never rows).
         */
        Overview: {
            employees: components["schemas"]["EmployeeCounts"];
            projects: components["schemas"]["ProjectCounts"];
            roles: components["schemas"]["RoleCounts"];
            match_runs: components["schemas"]["MatchRunCounts"];
        };
        /** PasswordChange */
        PasswordChange: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
        };
        /** ProfileJobOut */
        ProfileJobOut: {
            /** Title */
            title: string | null;
            /** Company */
            company: string | null;
            /** Start Date */
            start_date: string | null;
            /** End Date */
            end_date: string | null;
            /** Is Current */
            is_current: boolean;
            /** Description */
            description: string | null;
        };
        /** ProfileOut */
        ProfileOut: {
            /** Resume Id */
            resume_id: number;
            /** Employee Code */
            employee_code: string;
            /** Employee Name */
            employee_name: string;
            /** Status */
            status: string;
            /** Extraction Model */
            extraction_model: string | null;
            /** Headline */
            headline: string | null;
            /** Summary */
            summary: string | null;
            /** Total Experience Years */
            total_experience_years: number | null;
            /** Skills */
            skills: components["schemas"]["ProfileSkillOut"][];
            /** Experience */
            experience: components["schemas"]["ProfileJobOut"][];
            /** Education */
            education: {
                [key: string]: unknown;
            }[];
            /** Certifications */
            certifications: string[];
            /** Rejected Skills */
            rejected_skills: {
                [key: string]: unknown;
            }[];
            /** Warnings */
            warnings: string[];
            /** Stats */
            stats: {
                [key: string]: unknown;
            } | null;
        };
        /** ProfileSkillOut */
        ProfileSkillOut: {
            /** Name */
            name: string;
            /** Category */
            category: string | null;
            /** Years */
            years: number | null;
            /** Last Used Year */
            last_used_year: number | null;
            /** Evidence */
            evidence: string | null;
        };
        /** ProjectCounts */
        ProjectCounts: {
            /** Total */
            total: number;
            /** By Status */
            by_status: {
                [key: string]: number;
            };
        };
        /** ProjectCreate */
        ProjectCreate: {
            /** Name */
            name: string;
            /** Client Name */
            client_name?: string | null;
            /** Description */
            description?: string | null;
            /** @default planned */
            status: components["schemas"]["ProjectStatus"];
            /** Start Date */
            start_date?: string | null;
            /** End Date */
            end_date?: string | null;
        };
        /** ProjectOut */
        ProjectOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Client Name */
            client_name: string | null;
            /** Description */
            description: string | null;
            status: components["schemas"]["ProjectStatus"];
            /** Start Date */
            start_date: string | null;
            /** End Date */
            end_date: string | null;
            /**
             * Roles
             * @default []
             */
            roles: components["schemas"]["RoleOut"][];
        };
        /**
         * ProjectStatus
         * @enum {string}
         */
        ProjectStatus: "planned" | "active" | "on_hold" | "completed";
        /** QueueStats */
        QueueStats: {
            /** Total */
            total: number;
            /** By Status */
            by_status: {
                [key: string]: number;
            };
            /** Worker Running */
            worker_running: boolean;
            /**
             * Vector Count
             * @default 0
             */
            vector_count: number;
        };
        /** RequiredSkill */
        RequiredSkill: {
            /** Name */
            name: string;
            /** Min Years */
            min_years?: number | null;
            /** As Written */
            as_written?: string | null;
        };
        /**
         * Requirements
         * @description Parsed by the LLM, and editable by a person (PUT) when the AI got something wrong.
         */
        Requirements: {
            /** Title */
            title?: string | null;
            /**
             * Seniority
             * @default unspecified
             * @enum {string}
             */
            seniority: "junior" | "mid" | "senior" | "lead" | "principal" | "unspecified";
            /**
             * Must Have
             * @default []
             */
            must_have: components["schemas"]["RequiredSkill"][];
            /**
             * Nice To Have
             * @default []
             */
            nice_to_have: components["schemas"]["RequiredSkill"][];
            /** Min Total Years */
            min_total_years?: number | null;
            /** Location */
            location?: string | null;
            /**
             * Domain
             * @default []
             */
            domain: string[];
            /**
             * Search Summary
             * @default
             */
            search_summary: string;
            /** Parsed By */
            parsed_by?: string | null;
            /** Parsed At */
            parsed_at?: string | null;
            /**
             * Edited By User
             * @default false
             */
            edited_by_user: boolean;
        };
        /** ResumeDetail */
        ResumeDetail: {
            /** Id */
            id: number;
            /** Employee Id */
            employee_id: number;
            /** Original Filename */
            original_filename: string;
            /** Mime Type */
            mime_type: string;
            /** File Size Bytes */
            file_size_bytes: number;
            /** Is Current */
            is_current: boolean;
            status: components["schemas"]["ResumeStatus"];
            /** Error Message */
            error_message: string | null;
            /** Attempts */
            attempts: number;
            /** Page Count */
            page_count: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Processed At */
            processed_at: string | null;
            /** Employee Code */
            employee_code: string;
            /** Employee Name */
            employee_name: string;
            /** Text Length */
            text_length: number;
            /** Text */
            text: string | null;
        };
        /** ResumeOut */
        ResumeOut: {
            /** Id */
            id: number;
            /** Employee Id */
            employee_id: number;
            /** Original Filename */
            original_filename: string;
            /** Mime Type */
            mime_type: string;
            /** File Size Bytes */
            file_size_bytes: number;
            /** Is Current */
            is_current: boolean;
            status: components["schemas"]["ResumeStatus"];
            /** Error Message */
            error_message: string | null;
            /** Attempts */
            attempts: number;
            /** Page Count */
            page_count: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Processed At */
            processed_at: string | null;
        };
        /**
         * ResumeStatus
         * @enum {string}
         */
        ResumeStatus: "queued" | "parsing" | "parsed" | "extracting" | "extracted" | "embedding" | "ready" | "failed";
        /** RoleCounts */
        RoleCounts: {
            /** Total */
            total: number;
            /** By Status */
            by_status: {
                [key: string]: number;
            };
            /** Parsed */
            parsed: number;
        };
        /** RoleCreate */
        RoleCreate: {
            /**
             * Title
             * @example DevOps / Platform Engineer (Kubernetes)
             */
            title: string;
            /**
             * Description
             * @example Platform engineer to migrate 60 services to Kubernetes on AWS...
             */
            description: string;
            /** Location */
            location?: string | null;
            /**
             * Allocation Percent
             * @default 100
             */
            allocation_percent: number;
            /** Start Date */
            start_date?: string | null;
            /**
             * Headcount
             * @default 1
             */
            headcount: number;
            /** Min Experience Years */
            min_experience_years?: number | null;
        };
        /** RoleOut */
        RoleOut: {
            /** Id */
            id: number;
            /** Project Id */
            project_id: number;
            /** Title */
            title: string;
            /** Description */
            description: string;
            /** Location */
            location: string | null;
            /** Allocation Percent */
            allocation_percent: number;
            /** Start Date */
            start_date: string | null;
            /** Headcount */
            headcount: number;
            /** Min Experience Years */
            min_experience_years: number | null;
            status: components["schemas"]["RoleStatus"];
            requirements: components["schemas"]["Requirements"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * RoleStatus
         * @enum {string}
         */
        RoleStatus: "open" | "filled" | "closed";
        /** RowError */
        RowError: {
            /** Line */
            line: number;
            /** Employee Code */
            employee_code: string | null;
            /** Message */
            message: string;
        };
        /** SemanticSearchRequest */
        SemanticSearchRequest: {
            /**
             * Query
             * @example container orchestration and infrastructure as code
             */
            query: string;
            /**
             * Top K
             * @description How many employees to return
             * @default 10
             */
            top_k: number;
        };
        /** SemanticSearchResponse */
        SemanticSearchResponse: {
            /** Query */
            query: string;
            /** Results */
            results: components["schemas"]["EmployeeResult"][];
            /** Timings */
            timings: {
                [key: string]: unknown;
            };
        };
        /** SimilarityRequest */
        SimilarityRequest: {
            /**
             * Text A
             * @example Looking for a backend developer with Django experience
             */
            text_a: string;
            /**
             * Text B
             * @example Built REST APIs in Python for 4 years
             */
            text_b: string;
            /**
             * Use Prefixes
             * @description Add nomic's search_query:/search_document: prefixes
             * @default true
             */
            use_prefixes: boolean;
        };
        /** SkillMatchOut */
        SkillMatchOut: {
            /** Required */
            required: string;
            /** Matched With */
            matched_with: string;
            /** Direct */
            direct: boolean;
            /** Years */
            years: number | null;
            /** Last Used Year */
            last_used_year: number | null;
            /** Credit */
            credit: number;
            /** Evidence */
            evidence: string | null;
            /** Weight */
            weight: number;
        };
        /** TokenResponse */
        TokenResponse: {
            /** Access Token */
            access_token: string;
            /**
             * Token Type
             * @default bearer
             */
            token_type: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            user: components["schemas"]["UserOut"];
        };
        /** UploadItemResult */
        UploadItemResult: {
            /** Filename */
            filename: string;
            /** Ok */
            ok: boolean;
            /** Resume Id */
            resume_id?: number | null;
            /** Employee Code */
            employee_code?: string | null;
            /** Error */
            error?: string | null;
        };
        /** UserCreate */
        UserCreate: {
            /**
             * Email
             * @example manager@company.local
             */
            email: string;
            /** Full Name */
            full_name: string;
            /** @default resource_manager */
            role: components["schemas"]["UserRole"];
            /** Password */
            password: string;
        };
        /** UserOut */
        UserOut: {
            /** Id */
            id: number;
            /** Email */
            email: string;
            /** Full Name */
            full_name: string;
            role: components["schemas"]["UserRole"];
            /** Is Active */
            is_active: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * UserRole
         * @enum {string}
         */
        UserRole: "admin" | "resource_manager";
        /**
         * UserUpdate
         * @description Only the fields you send are changed.
         */
        UserUpdate: {
            /** Full Name */
            full_name?: string | null;
            role?: components["schemas"]["UserRole"] | null;
            /** Is Active */
            is_active?: boolean | null;
            /** Password */
            password?: string | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
            /** @description Database or Ollama unreachable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
        };
    };
    change_password_api_auth_change_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_users_api_users_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"][];
                };
            };
        };
    };
    create_user_api_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_user_api_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    overview_api_overview_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Overview"];
                };
            };
        };
    };
    import_employees_api_employees_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_employees_api_employees_import_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmployeeImportResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_employees_api_employees_get: {
        parameters: {
            query?: {
                /** @description Matches code, name, department or location */
                search?: string | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmployeeListItem"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_employee_api_employees__employee_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                employee_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmployeeDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_resume_api_employees__employee_id__resumes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                employee_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_resume_api_employees__employee_id__resumes_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    bulk_upload_api_resumes_bulk_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_bulk_upload_api_resumes_bulk_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkUploadResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_resumes_api_resumes_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["ResumeStatus"] | null;
                current_only?: boolean;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    queue_stats_api_resumes_stats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QueueStats"];
                };
            };
        };
    };
    reextract_all_api_resumes_reextract_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    reembed_all_api_resumes_reembed_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_resume_api_resumes__resume_id__get: {
        parameters: {
            query?: {
                full_text?: boolean;
            };
            header?: never;
            path: {
                resume_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_api_resumes__resume_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_profile_api_resumes__resume_id__profile_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_api_resumes__resume_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_semantic_api_search_semantic_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SemanticSearchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SemanticSearchResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resume_chunks_api_resumes__resume_id__chunks_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_projects_api_projects_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"][];
                };
            };
        };
    };
    create_project_api_projects_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_role_api_projects__project_id__roles_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RoleCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RoleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_role_api_roles__role_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RoleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    parse_requirements_api_roles__role_id__requirements_parse_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RoleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_requirements_api_roles__role_id__requirements_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Requirements"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RoleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    find_candidates_api_roles__role_id__candidates_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CandidatesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CandidatesResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_match_api_roles__role_id__match_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchRunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_match_run_api_match_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchRunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_match_runs_api_roles__role_id__match_runs_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchRunSummary"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_conversations_api_agent_conversations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"][];
                };
            };
        };
    };
    create_conversation_api_agent_conversations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConversationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_api_agent_conversations__conversation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_conversation_api_agent_conversations__conversation_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ask_api_agent_conversations__conversation_id__messages_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AskRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AskResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dev_chat_api_dev_chat_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChatRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChatResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dev_similarity_api_dev_similarity_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimilarityRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dev_extract_api_dev_extract__resume_id__post: {
        parameters: {
            query?: {
                model?: "fast" | "quality";
            };
            header?: never;
            path: {
                resume_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    root__get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
