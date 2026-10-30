import { Sparkles } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { STATUS_LABEL } from "@/features/resumes/labels";
import type { Profile, Resume } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

import { getProfile } from "../queries";

/**
 * What the AI extracted from the current resume (Step 5): headline, summary, skills with years and a
 * QUOTE from the resume as evidence, jobs, education. Showing the evidence is the point: a resource
 * manager can see WHY the system believes someone knows Kubernetes, and spot a wrong extraction.
 */
export async function ProfileSections({ resume }: { resume: Resume | undefined }) {
  if (!resume) {
    return (
      <Card>
        <CardContent>
          <EmptyState icon={Sparkles} title="No resume yet">
            Upload a resume to get an AI profile for this person.
          </EmptyState>
        </CardContent>
      </Card>
    );
  }
  const result = await getProfile(resume.id);
  if (!result.ok) {
    return (
      <Card>
        <CardContent>
          <EmptyState icon={Sparkles} title="No AI profile yet">
            {result.status === 404
              ? `The current resume is at "${STATUS_LABEL[resume.status]}". The profile appears once the AI has read it.`
              : result.message}
          </EmptyState>
        </CardContent>
      </Card>
    );
  }
  const profile = result.data;
  return (
    <div className="space-y-6">
      <Summary profile={profile} />
      <Skills profile={profile} />
      <Experience profile={profile} />
      <Education profile={profile} />
    </div>
  );
}

function Summary({ profile }: { profile: Profile }) {
  return (
    <Card>
      <CardHeader>
        <div className="space-y-1">
          <CardTitle>{profile.headline ?? "Profile"}</CardTitle>
          <CardDescription>
            {profile.total_experience_years !== null && `${profile.total_experience_years} years of experience · `}
            extracted by {profile.extraction_model ?? "the AI"}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {profile.summary && <p className="text-sm leading-relaxed">{profile.summary}</p>}
        {profile.warnings.length > 0 && (
          <Alert tone="warning" title="Checks flagged during extraction">
            <ul className="list-disc space-y-0.5 pl-5">
              {profile.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

function Skills({ profile }: { profile: Profile }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Skills</CardTitle>
        <CardAction>
          <Badge>{profile.skills.length}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        {profile.skills.length === 0 ? (
          <p className="text-sm text-muted-foreground">No skills were found.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Skill</TableHead>
                <TableHead className="text-right">Years</TableHead>
                <TableHead className="text-right">Last used</TableHead>
                <TableHead>Evidence from the resume</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {profile.skills.map((skill) => (
                <TableRow key={skill.name}>
                  <TableCell className="font-medium whitespace-nowrap">
                    {skill.name}
                    {skill.category && (
                      <span className="block text-xs font-normal text-muted-foreground">{skill.category}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{skill.years ?? "–"}</TableCell>
                  <TableCell className="text-right tabular-nums">{skill.last_used_year ?? "–"}</TableCell>
                  <TableCell className="max-w-md text-xs text-muted-foreground">
                    {skill.evidence ? <q>{skill.evidence}</q> : "–"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function Experience({ profile }: { profile: Profile }) {
  if (profile.experience.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Experience</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-4 border-l pl-4">
          {profile.experience.map((job, index) => (
            <li key={`${job.company}-${job.start_date}-${index}`} className="relative">
              <span className="absolute top-1.5 -left-[1.3rem] size-2 rounded-full bg-primary" aria-hidden />
              <p className="text-sm font-medium">
                {job.title ?? "Role"}
                {job.company && <span className="font-normal text-muted-foreground"> · {job.company}</span>}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatDate(job.start_date) || "?"} – {job.is_current ? "now" : formatDate(job.end_date) || "?"}
              </p>
              {job.description && <p className="mt-1 text-sm text-muted-foreground">{job.description}</p>}
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function Education({ profile }: { profile: Profile }) {
  if (profile.education.length === 0 && profile.certifications.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Education and certifications</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 text-sm sm:grid-cols-2">
        <ul className="space-y-2">
          {profile.education.map((item, index) => (
            <li key={index}>
              <span className="font-medium">{item.degree ?? "Degree"}</span>
              <span className="block text-muted-foreground">
                {[item.institution, item.year].filter(Boolean).join(" · ")}
              </span>
            </li>
          ))}
        </ul>
        {profile.certifications.length > 0 && (
          <ul className="flex flex-wrap content-start gap-1.5">
            {profile.certifications.map((cert) => (
              <li key={cert}>
                <Badge tone="info">{cert}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading the profile">
      <Skeleton className="h-36 w-full rounded-xl" />
      <Skeleton className="h-72 w-full rounded-xl" />
    </div>
  );
}
