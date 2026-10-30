"use client";

import { ArrowDown, ArrowUp, Pencil, Plus, Sparkles, X } from "lucide-react";
import { useActionState, useState } from "react";

import { ActionButton } from "@/components/action-button";
import { SubmitButton } from "@/components/submit-button";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { Requirements } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

import { parseRequirements, saveRequirements } from "../actions";
import { SENIORITY } from "../labels";
import type { FormState, RequirementsInput } from "../schemas";

type Skill = { name: string; min_years: number | null };

const toSkills = (list: Requirements["must_have"] | undefined): Skill[] =>
  (list ?? []).map((s) => ({ name: s.name, min_years: s.min_years ?? null }));

/**
 * What the role needs, as the AI understood it from the description (Step 7), and the place to fix it.
 *
 * Two modes:
 *   - view: must-haves, nice-to-haves (with minimum years), seniority, location, domain, the search
 *     summary used for vector search, who parsed it and whether a person edited it;
 *   - edit: change anything, move a skill between must-have and nice-to-have, add or remove skills.
 * Matching always uses what is shown here, so a wrong AI reading is fixed BEFORE it ranks people.
 */
export function RequirementsPanel({ roleId, requirements }: { roleId: number; requirements: Requirements | null }) {
  const [editing, setEditing] = useState(false);

  if (!requirements) {
    return (
      <div className="space-y-3">
        <Alert tone="info" title="Not read yet">
          Let the AI read the role description and list the must-have and nice-to-have skills. It takes 30-60 seconds,
          once; you can correct the result afterwards.
        </Alert>
        <ActionButton
          action={parseRequirements.bind(null, roleId)}
          label="Read the description with AI"
          pendingLabel="The AI is reading… (up to a minute)"
          variant="default"
          size="default"
        />
      </div>
    );
  }

  if (editing) {
    return <RequirementsEditor roleId={roleId} requirements={requirements} onDone={() => setEditing(false)} />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Sparkles className="size-3.5" aria-hidden />
        Read by {requirements.parsed_by ?? "the AI"}
        {requirements.parsed_at && ` on ${formatDateTime(requirements.parsed_at)}`}
        {requirements.edited_by_user && <Badge tone="info">corrected by a person</Badge>}
      </div>

      <SkillGroup title="Must have" skills={toSkills(requirements.must_have)} tone="info" />
      <SkillGroup title="Nice to have" skills={toSkills(requirements.nice_to_have)} tone="neutral" />

      <dl className="grid gap-3 text-sm sm:grid-cols-3">
        <Fact label="Seniority" value={requirements.seniority === "unspecified" ? "–" : requirements.seniority} />
        <Fact
          label="Minimum total experience"
          value={requirements.min_total_years != null ? `${requirements.min_total_years} years` : "–"}
        />
        <Fact label="Location" value={requirements.location ?? "anywhere"} />
        <Fact label="Domain" value={(requirements.domain ?? []).join(", ") || "–"} className="sm:col-span-3" />
      </dl>

      {requirements.search_summary && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">Search summary (used for meaning-based search)</p>
          <p className="text-sm">{requirements.search_summary}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t pt-4">
        <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
          <Pencil aria-hidden /> Correct
        </Button>
        <ActionButton
          action={parseRequirements.bind(null, roleId)}
          label="Read again with AI"
          pendingLabel="The AI is reading…"
          variant="ghost"
          confirm={{
            title: "Read the description again?",
            description:
              "The AI's new reading replaces the current requirements, including any corrections made by a person. Earlier match runs keep the requirements they used.",
            confirmLabel: "Read again",
          }}
        />
      </div>
    </div>
  );
}

function SkillGroup({ title, skills, tone }: { title: string; skills: Skill[]; tone: "info" | "neutral" }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">
        {title} ({skills.length})
      </p>
      {skills.length === 0 ? (
        <p className="text-sm text-muted-foreground">None</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {skills.map((skill) => (
            <li key={skill.name}>
              <Badge tone={tone} className="px-2.5 py-1 text-sm">
                {skill.name}
                {skill.min_years != null && <span className="opacity-70">· {skill.min_years}+ y</span>}
              </Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Fact({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="first-letter:uppercase">{value}</dd>
    </div>
  );
}

function RequirementsEditor({
  roleId,
  requirements,
  onDone,
}: {
  roleId: number;
  requirements: Requirements;
  onDone: () => void;
}) {
  const [must, setMust] = useState<Skill[]>(toSkills(requirements.must_have));
  const [nice, setNice] = useState<Skill[]>(toSkills(requirements.nice_to_have));
  const [seniority, setSeniority] = useState<string>(requirements.seniority ?? "unspecified");
  const [minYears, setMinYears] = useState(requirements.min_total_years?.toString() ?? "");
  const [location, setLocation] = useState(requirements.location ?? "");
  const [domain, setDomain] = useState((requirements.domain ?? []).join(", "));
  const [summary, setSummary] = useState(requirements.search_summary ?? "");
  const [state, formAction] = useActionState<FormState, FormData>(saveRequirements.bind(null, roleId), {});

  // Everything the server needs, as one JSON value; the Server Action validates it with zod.
  const payload: RequirementsInput = {
    seniority: seniority as RequirementsInput["seniority"],
    must_have: must.filter((s) => s.name.trim()),
    nice_to_have: nice.filter((s) => s.name.trim()),
    min_total_years: minYears === "" ? null : Number(minYears),
    location: location.trim() || null,
    domain: domain
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean),
    search_summary: summary,
  };

  const move = (skill: Skill, from: "must" | "nice") => {
    if (from === "must") {
      setMust(must.filter((s) => s !== skill));
      setNice([...nice, skill]);
    } else {
      setNice(nice.filter((s) => s !== skill));
      setMust([...must, skill]);
    }
  };

  return (
    <form action={formAction} className="space-y-5">
      <input type="hidden" name="payload" value={JSON.stringify(payload)} />
      {state.message && <Alert tone={state.ok ? "info" : "danger"}>{state.message}</Alert>}

      <SkillEditor
        title="Must have"
        skills={must}
        onChange={setMust}
        moveLabel="Make nice-to-have"
        moveIcon={<ArrowDown aria-hidden />}
        onMove={(s) => move(s, "must")}
      />
      <SkillEditor
        title="Nice to have"
        skills={nice}
        onChange={setNice}
        moveLabel="Make must-have"
        moveIcon={<ArrowUp aria-hidden />}
        onMove={(s) => move(s, "nice")}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="req-seniority">Seniority</Label>
          <NativeSelect id="req-seniority" value={seniority} onChange={(e) => setSeniority(e.target.value)}>
            {SENIORITY.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="req-years">Minimum total years</Label>
          <Input
            id="req-years"
            type="number"
            min={0}
            max={50}
            step={0.5}
            value={minYears}
            onChange={(e) => setMinYears(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="req-location">Location</Label>
          <Input
            id="req-location"
            value={location}
            maxLength={100}
            placeholder="anywhere"
            onChange={(e) => setLocation(e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="req-domain">Domain (comma-separated)</Label>
        <Input
          id="req-domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="insurance, claims"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="req-summary">Search summary</Label>
        <Textarea id="req-summary" rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} />
        <p className="text-xs text-muted-foreground">
          One or two sentences about the ideal person; turned into a vector for meaning-based search.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 border-t pt-4">
        <SubmitButton pendingLabel="Saving…">Save requirements</SubmitButton>
        <Button type="button" variant="ghost" onClick={onDone}>
          {state.ok ? "Done" : "Cancel"}
        </Button>
      </div>
    </form>
  );
}

function SkillEditor({
  title,
  skills,
  onChange,
  moveLabel,
  moveIcon,
  onMove,
}: {
  title: string;
  skills: Skill[];
  onChange: (skills: Skill[]) => void;
  moveLabel: string;
  moveIcon: React.ReactNode;
  onMove: (skill: Skill) => void;
}) {
  const update = (index: number, patch: Partial<Skill>) =>
    onChange(skills.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  return (
    <fieldset className="space-y-2">
      <legend className="text-xs font-medium text-muted-foreground">{title}</legend>
      {skills.map((skill, index) => (
        <div key={index} className="flex items-center gap-2">
          <Input
            aria-label={`${title}: skill ${index + 1}`}
            value={skill.name}
            maxLength={100}
            onChange={(e) => update(index, { name: e.target.value })}
            className="flex-1"
          />
          <Input
            aria-label={`${title}: minimum years for ${skill.name || `skill ${index + 1}`}`}
            type="number"
            min={0}
            max={50}
            step={0.5}
            placeholder="years"
            value={skill.min_years ?? ""}
            onChange={(e) => update(index, { min_years: e.target.value === "" ? null : Number(e.target.value) })}
            className="w-24"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            title={moveLabel}
            aria-label={`${moveLabel}: ${skill.name}`}
            onClick={() => onMove(skill)}
          >
            {moveIcon}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Remove ${skill.name || `skill ${index + 1}`}`}
            onClick={() => onChange(skills.filter((_, i) => i !== index))}
          >
            <X aria-hidden />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...skills, { name: "", min_years: null }])}
      >
        <Plus aria-hidden /> Add skill
      </Button>
    </fieldset>
  );
}
