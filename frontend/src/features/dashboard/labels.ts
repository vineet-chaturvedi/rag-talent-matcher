/** The keys of /api/health's "models" object, as people say them. */
export const MODEL_LABEL: Record<string, string> = {
  embed_model: "Embedding model",
  fast_llm_model: "Fast LLM",
  quality_llm_model: "Quality LLM",
  // Shown only when a task uses its own model instead of "fast" / "quality" (*_MODEL_ROLE in .env)
  extraction_model: "Resume extraction model",
  role_parse_model: "Role reading model",
  judge_model: "Judge model",
  agent_model: "Assistant model",
};
