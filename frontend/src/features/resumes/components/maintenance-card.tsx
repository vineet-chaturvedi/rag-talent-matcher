import { ActionButton } from "@/components/action-button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { reembedAll, reextractAll } from "../actions";

/**
 * Whole-knowledge-base actions, used after changing a model, a prompt or the chunking settings.
 * Both only QUEUE work; the background worker does it (CPU-only: minutes for 15 resumes, hours for
 * thousands), and the list above shows the progress live.
 */
export function MaintenanceCard() {
  return (
    <Card>
      <CardHeader>
        <div className="space-y-1">
          <CardTitle>Maintenance</CardTitle>
          <CardDescription>Rebuild the AI data after changing a model, prompt or chunking setting.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2 text-sm">
          <p className="font-medium">Re-extract all profiles</p>
          <p className="text-muted-foreground">
            The LLM reads every resume again (Step 5), then it is re-indexed. Slowest: about a minute per resume.
          </p>
          <ActionButton
            action={reextractAll}
            label="Re-extract all"
            pendingLabel="Queuing…"
            confirm={{
              title: "Re-extract every resume?",
              description:
                "Every current resume goes back to AI reading. Profiles, skills and search results update as the worker finishes each one. Matching keeps working meanwhile, on the old data until each resume is done.",
              confirmLabel: "Re-extract all",
            }}
          />
        </div>
        <div className="space-y-2 text-sm">
          <p className="font-medium">Re-index all</p>
          <p className="text-muted-foreground">
            Rebuild chunks, embeddings and the keyword index (Step 6) from the stored profiles. Fast: seconds per
            resume.
          </p>
          <ActionButton
            action={reembedAll}
            label="Re-index all"
            pendingLabel="Queuing…"
            confirm={{
              title: "Re-index every resume?",
              description:
                "Chunks and vectors are rebuilt from the stored text and profiles. The AI profiles stay as they are.",
              confirmLabel: "Re-index all",
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
