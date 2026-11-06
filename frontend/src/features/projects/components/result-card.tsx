import { CircleCheck, CircleHelp, LoaderCircle, TriangleAlert } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { FeedbackButtons } from "@/features/feedback/components/feedback-buttons";
import type { MatchResult, SkillMatch } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

import { MET, RATING_TONE } from "../labels";
import { ScoreBar } from "./score-bar";

/**
 * One ranked candidate, built entirely from what the run stored (nothing is recomputed):
 *   - the final score, and how it was made (rule score from Step 8, the judge's score, the factors);
 *   - availability for this role;
 *   - must-haves: matched (with years and the resume quote) or missing; nice-to-haves;
 *   - the LLM judge's verdict per must-have, with its quote and whether CODE found that quote in the
 *     resume. "Verified" is the whole point: an unverified "yes" was already downgraded to "partly";
 *   - 👍 / 👎 so the people who know the candidates can say whether the ranking is right (Step 14c).
 * Long details sit in <details> elements: native, keyboard-accessible, and no JavaScript needed.
 */
export function ResultCard({ result, judgeWeight }: { result: MatchResult; judgeWeight: number }) {
  const { score_breakdown: score, explanation } = result;
  const { facts, judge, judge_status } = explanation;
  const availability = facts.availability;

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-start gap-4">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-accent-foreground">
            {result.rank}
          </span>
          <div className="min-w-0 flex-1">
            <Link href={`/employees/${result.employee_id}` as Route} className="font-medium hover:underline">
              {result.full_name}
            </Link>
            <p className="text-sm text-muted-foreground">
              {result.employee_code}
              {result.designation && ` · ${result.designation}`}
              {result.location && ` · ${result.location}`}
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-semibold tabular-nums">{result.final_score.toFixed(2)}</p>
            <p className="text-xs text-muted-foreground">final score</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {judge && <Badge tone={RATING_TONE[judge.rating]}>Judge: {judge.rating}</Badge>}
          {judge_status === "pending" && (
            <Badge tone="info">
              <LoaderCircle className="animate-spin" aria-hidden /> waiting for the judge
            </Badge>
          )}
          {judge_status === "not_requested" && <Badge>rules only</Badge>}
          {availability && (
            <Badge tone={availability.fits ? "success" : "warning"}>
              {availability.fits ? "available" : "availability conflict"}
            </Badge>
          )}
          {availability && <span className="text-xs text-muted-foreground">{availability.note}</span>}
          {availability?.available_from && !availability.fits && (
            <span className="text-xs text-muted-foreground">free from {formatDate(availability.available_from)}</span>
          )}
        </div>

        {judge && <p className="text-sm">{judge.summary}</p>}
        {judge_status === "failed" && (
          <Alert tone="warning" title="The judge could not assess this candidate">
            {explanation.judge_error ?? "Unknown error."} The rule score is used instead.
          </Alert>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <SkillFacts
            must={facts.must_matched ?? []}
            missing={facts.must_missing ?? []}
            nice={facts.nice_matched ?? []}
          />
          <div className="space-y-2">
            <ScoreBar label="Skills" value={score.skills} />
            <ScoreBar label="Relevance" value={score.relevance} />
            <ScoreBar label="Rule score" value={score.rule_score} />
            {score.judge_score != null && <ScoreBar label="Judge score" value={score.judge_score} />}
            <p className="pt-1 text-xs text-muted-foreground">
              {score.judge_score != null
                ? `Final = ${(1 - judgeWeight).toFixed(1)} × rule + ${judgeWeight.toFixed(1)} × judge.`
                : "Final = rule score (no judge verdict)."}{" "}
              Factors: experience ×{score.factors.experience}, availability ×{score.factors.availability}, location ×
              {score.factors.location}.{score.total_years != null && ` ${score.total_years} years in total`}
              {score.required_years != null && ` (role asks ${score.required_years}).`}
            </p>
          </div>
        </div>

        {judge && judge.must_haves.length > 0 && (
          <details className="group rounded-lg border" open={result.rank <= 3}>
            <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium select-none">
              The judge&apos;s assessment · {judge.quotes_verified} of {judge.quotes_total} quotes found in the resume
            </summary>
            <div className="space-y-4 border-t px-4 py-3">
              <ul className="space-y-3">
                {judge.must_haves.map((m) => (
                  <li key={m.requirement} className="space-y-1 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{m.requirement}</span>
                      <Badge tone={MET[m.met].tone}>{MET[m.met].label}</Badge>
                      {m.claimed && m.claimed !== m.met && (
                        <span className="text-xs text-muted-foreground">
                          (the model said &ldquo;{m.claimed}&rdquo;, but its quote was not in the resume)
                        </span>
                      )}
                    </div>
                    {m.quote && <Quote text={m.quote} verified={m.verified} />}
                    {m.note && <p className="text-xs text-muted-foreground">{m.note}</p>}
                  </li>
                ))}
              </ul>
              {judge.strengths.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Strengths</p>
                  <ul className="space-y-2">
                    {judge.strengths.map((s) => (
                      <li key={s.point} className="space-y-1 text-sm">
                        <span>{s.point}</span>
                        {s.quote && <Quote text={s.quote} verified={s.verified} />}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {judge.gaps.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Gaps</p>
                  <ul className="list-disc space-y-0.5 pl-5 text-sm">
                    {judge.gaps.map((g) => (
                      <li key={g}>{g}</li>
                    ))}
                  </ul>
                </div>
              )}
              {judge.stats && (
                <p className="text-xs text-muted-foreground">
                  {judge.stats.model} · {judge.stats.seconds} s · {judge.stats.prompt_tokens} prompt tokens,{" "}
                  {judge.stats.output_tokens} answer tokens
                </p>
              )}
            </div>
          </details>
        )}

        {(facts.keyword_snippets ?? []).length > 0 && (
          <details className="rounded-lg border">
            <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium select-none">
              Where the keywords matched
            </summary>
            <ul className="space-y-2 border-t px-4 py-3 text-xs text-muted-foreground">
              {(facts.keyword_snippets ?? []).map((snippet) => (
                <li key={snippet} className="whitespace-pre-line">
                  <Highlighted text={snippet} />
                </li>
              ))}
            </ul>
          </details>
        )}

        {result.result_id != null && (
          <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
            <FeedbackButtons target="match" id={result.result_id} initial={result.my_feedback} />
            {(result.feedback_up > 0 || result.feedback_down > 0) && (
              <p className="text-xs text-muted-foreground">
                Team: {result.feedback_up} 👍 · {result.feedback_down} 👎
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SkillFacts({ must, missing, nice }: { must: SkillMatch[]; missing: string[]; nice: SkillMatch[] }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground">
          Must-haves: {must.length} of {must.length + missing.length} found in the profile
        </p>
        <ul className="space-y-1">
          {must.map((m) => (
            <SkillLine key={m.required} skill={m} />
          ))}
          {missing.map((name) => (
            <li key={name} className="flex items-center gap-2 text-destructive">
              <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
              {name} <span className="text-xs">missing</span>
            </li>
          ))}
        </ul>
      </div>
      {nice.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Nice-to-haves found</p>
          <ul className="space-y-1">
            {nice.map((m) => (
              <SkillLine key={m.required} skill={m} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SkillLine({ skill }: { skill: SkillMatch }) {
  return (
    <li className="flex items-start gap-2" title={skill.evidence ?? undefined}>
      <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden />
      <span>
        {skill.required}
        {!skill.direct && <span className="text-muted-foreground"> (via {skill.matched_with})</span>}
        <span className="text-xs text-muted-foreground">
          {skill.years != null &&
            (skill.years_basis === "estimated" ? ` · ≈ ${skill.years} y (estimated)` : ` · ${skill.years} y`)}
          {skill.years == null && (skill.uses ?? 0) > 0 && ` · ${skill.uses} project${skill.uses === 1 ? "" : "s"}`}
          {skill.last_used_year != null && ` · last ${skill.last_used_year}`}
        </span>
      </span>
    </li>
  );
}

function Quote({ text, verified }: { text: string; verified: boolean }) {
  return (
    <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
      {verified ? (
        <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-label="Found in the resume" />
      ) : (
        <CircleHelp className="mt-0.5 size-3.5 shrink-0 text-warning" aria-label="Not found in the resume" />
      )}
      <q>{text}</q>
      {!verified && <span className="shrink-0">(not found in the resume)</span>}
    </p>
  );
}

/** FTS5 marks matches as [word]; show them bold instead of with brackets. */
function Highlighted({ text }: { text: string }) {
  const parts = text.split(/(\[[^\]]+\])/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("[") && part.endsWith("]") ? (
          <mark key={i} className="rounded bg-primary/15 px-0.5 text-foreground">
            {part.slice(1, -1)}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}
